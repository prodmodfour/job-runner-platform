from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from job_runner_platform.database.models import JobModel
from job_runner_platform.domain.jobs import (
    DEFAULT_JOB_PRIORITY,
    DEFAULT_MAX_ATTEMPTS,
    JobId,
    JobPayload,
    JobPriority,
    JobResult,
    JobStatus,
    JobType,
    MaxAttempts,
)


class JobRepository:
    """Database access for persistent jobs.

    The repository owns all SQLAlchemy reads and writes for the jobs table. It
    intentionally performs state transitions only on existing allowlisted job
    records; it never executes user-provided commands, scripts, containers, or
    code strings.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_job(
        self,
        *,
        job_type: JobType,
        payload: JobPayload | None = None,
        priority: JobPriority = DEFAULT_JOB_PRIORITY,
        max_attempts: MaxAttempts = DEFAULT_MAX_ATTEMPTS,
        idempotency_key: str | None = None,
    ) -> JobModel:
        """Persist a queued allowlisted job and return the created row."""

        now = _utc_now()
        job = JobModel(
            job_type=job_type.value,
            status=JobStatus.QUEUED.value,
            priority=priority,
            payload=dict(payload or {}),
            attempts=0,
            max_attempts=max_attempts,
            idempotency_key=idempotency_key,
            created_at=now,
            updated_at=now,
            queued_at=now,
        )
        self._session.add(job)
        await self._session.flush()
        await self._session.refresh(job)
        return job

    async def get_job_by_id(self, job_id: JobId) -> JobModel | None:
        """Return a job by UUID, if it exists."""

        statement = select(JobModel).where(JobModel.id == job_id)
        return await self._one_or_none(statement)

    async def list_jobs(
        self,
        *,
        limit: int,
        offset: int,
        status: JobStatus | None = None,
    ) -> list[JobModel]:
        """Return a stable page of jobs, optionally filtered by status."""

        _validate_pagination(limit=limit, offset=offset)
        statement = select(JobModel)
        if status is not None:
            statement = statement.where(JobModel.status == status.value)
        statement = (
            statement.order_by(
                JobModel.created_at.desc(),
                JobModel.id.asc(),
            )
            .limit(limit)
            .offset(offset)
        )

        return list(await self._session.scalars(statement))

    async def find_by_idempotency_key(self, idempotency_key: str) -> JobModel | None:
        """Return the job associated with an idempotency key, if any."""

        statement = select(JobModel).where(
            JobModel.idempotency_key == idempotency_key,
        )
        return await self._one_or_none(statement)

    async def request_cancellation(self, job_id: JobId) -> JobModel | None:
        """Request cancellation for a queued or running job.

        Queued jobs are moved directly to ``cancelled`` because no worker has
        started them. Running jobs become ``cancel_requested`` so a future worker
        cancellation loop can cooperate safely. Terminal jobs are returned
        unchanged so the service layer can report a clear conflict later.
        """

        job = await self._locked_job_by_id(job_id)
        if job is None:
            return None

        now = _utc_now()
        if job.status == JobStatus.QUEUED.value:
            job.status = JobStatus.CANCELLED.value
            job.finished_at = now
            job.lease_owner = None
            job.lease_expires_at = None
            job.updated_at = now
            await self._session.flush()
            return job

        if job.status == JobStatus.RUNNING.value:
            job.status = JobStatus.CANCEL_REQUESTED.value
            job.updated_at = now
            await self._session.flush()
            return job

        return job

    async def claim_queued_job(
        self,
        *,
        job_id: JobId,
        worker_id: str,
        lease_expires_at: datetime,
    ) -> JobModel | None:
        """Claim a queued job for a worker if it has not already been claimed.

        The row is selected with ``FOR UPDATE`` on databases that support row
        locks. A duplicate Redis message or competing worker that observes an
        already-running/non-queued job receives ``None``.
        """

        _ensure_aware_datetime(lease_expires_at, "lease_expires_at")
        job = await self._locked_job_by_id(job_id)
        if job is None or job.status != JobStatus.QUEUED.value:
            return None

        now = _utc_now()
        job.status = JobStatus.RUNNING.value
        job.attempts += 1
        job.started_at = now
        job.finished_at = None
        job.lease_owner = worker_id
        job.lease_expires_at = lease_expires_at
        job.updated_at = now
        await self._session.flush()
        return job

    async def complete_job(
        self,
        *,
        job_id: JobId,
        result: JobResult | None = None,
    ) -> JobModel | None:
        """Mark a running job as succeeded and store its safe JSON result."""

        job = await self._locked_job_by_id(job_id)
        if job is None or job.status != JobStatus.RUNNING.value:
            return None

        now = _utc_now()
        job.status = JobStatus.SUCCEEDED.value
        job.result = dict(result or {})
        job.error_message = None
        job.lease_owner = None
        job.lease_expires_at = None
        job.finished_at = now
        job.updated_at = now
        await self._session.flush()
        return job

    async def fail_job(
        self,
        *,
        job_id: JobId,
        error_message: str,
    ) -> JobModel | None:
        """Mark a running job as failed and persist a safe error message."""

        job = await self._locked_job_by_id(job_id)
        if job is None or job.status != JobStatus.RUNNING.value:
            return None

        now = _utc_now()
        job.status = JobStatus.FAILED.value
        job.error_message = error_message
        job.lease_owner = None
        job.lease_expires_at = None
        job.finished_at = now
        job.updated_at = now
        await self._session.flush()
        return job

    async def mark_dead_lettered(
        self,
        *,
        job_id: JobId,
        error_message: str,
    ) -> JobModel | None:
        """Move a running or failed job to the dead-letter terminal state."""

        job = await self._locked_job_by_id(job_id)
        if job is None or job.status not in {
            JobStatus.RUNNING.value,
            JobStatus.FAILED.value,
        }:
            return None

        now = _utc_now()
        job.status = JobStatus.DEAD_LETTERED.value
        job.error_message = error_message
        job.lease_owner = None
        job.lease_expires_at = None
        job.finished_at = now
        job.updated_at = now
        await self._session.flush()
        return job

    async def requeue_job(
        self,
        *,
        job_id: JobId,
        error_message: str | None = None,
    ) -> JobModel | None:
        """Return a running or failed job to the queued state for retry/recovery."""

        job = await self._locked_job_by_id(job_id)
        if job is None or job.status not in {
            JobStatus.RUNNING.value,
            JobStatus.FAILED.value,
        }:
            return None

        now = _utc_now()
        job.status = JobStatus.QUEUED.value
        job.result = None
        if error_message is not None:
            job.error_message = error_message
        job.lease_owner = None
        job.lease_expires_at = None
        job.started_at = None
        job.finished_at = None
        job.queued_at = now
        job.updated_at = now
        await self._session.flush()
        return job

    async def find_stale_leased_jobs(
        self,
        *,
        as_of: datetime | None = None,
        limit: int = 100,
    ) -> list[JobModel]:
        """Find running jobs whose leases have expired by ``as_of``."""

        _validate_limit(limit)
        cutoff = as_of or _utc_now()
        _ensure_aware_datetime(cutoff, "as_of")
        statement = (
            select(JobModel)
            .where(
                JobModel.status == JobStatus.RUNNING.value,
                JobModel.lease_expires_at.is_not(None),
                JobModel.lease_expires_at <= cutoff,
            )
            .order_by(JobModel.lease_expires_at.asc(), JobModel.id.asc())
            .limit(limit)
        )
        return list(await self._session.scalars(statement))

    async def _locked_job_by_id(self, job_id: JobId) -> JobModel | None:
        statement = select(JobModel).where(JobModel.id == job_id).with_for_update()
        return await self._one_or_none(statement)

    async def _one_or_none(self, statement: Select[tuple[JobModel]]) -> JobModel | None:
        return cast(JobModel | None, await self._session.scalar(statement))


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _ensure_aware_datetime(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        message = f"{field_name} must be timezone-aware"
        raise ValueError(message)


def _validate_pagination(*, limit: int, offset: int) -> None:
    _validate_limit(limit)
    if offset < 0:
        raise ValueError("offset must be greater than or equal to 0")


def _validate_limit(limit: int) -> None:
    if limit < 1:
        raise ValueError("limit must be greater than or equal to 1")
