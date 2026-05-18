from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Final, Protocol

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from job_runner_platform.database.models import JobModel
from job_runner_platform.database.session import session_scope
from job_runner_platform.domain.jobs import (
    JobId,
    JobPayload,
    JobResult,
    JobStatus,
    JobType,
)
from job_runner_platform.handlers import (
    CancellationCheck,
    JobCancellationRequestedError,
    JobHandlerContext,
    JobHandlerError,
    run_job_handler,
)
from job_runner_platform.queues import JobQueue
from job_runner_platform.repositories import JobRepository

MAX_RECORDED_ERROR_MESSAGE_LENGTH: Final[int] = 2048
DEFAULT_STALE_RECOVERY_LIMIT: Final[int] = 100


class JobHandlerRunner(Protocol):
    """Callable surface used by the worker to run allowlisted handlers."""

    async def __call__(
        self,
        job_type: JobType | str,
        payload: JobPayload | None = None,
        *,
        context: JobHandlerContext | None = None,
    ) -> JobResult:
        """Run one safe built-in handler and return a JSON-safe result."""


class WorkerProcessOutcome(StrEnum):
    """Outcomes for one worker polling cycle."""

    NO_MESSAGE = "no_message"
    CLAIM_SKIPPED = "claim_skipped"
    SUCCEEDED = "succeeded"
    RETRIED = "retried"
    DEAD_LETTERED = "dead_lettered"
    CANCELLED = "cancelled"
    RECORD_SKIPPED = "record_skipped"


@dataclass(frozen=True, slots=True)
class WorkerProcessResult:
    """Result from processing at most one queued dispatch signal."""

    outcome: WorkerProcessOutcome
    job_id: JobId | None = None
    job_status: JobStatus | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class StaleJobRecoveryResult:
    """Summary of one explicit stale lease recovery pass."""

    scanned: int
    requeued_job_ids: tuple[JobId, ...] = ()
    dead_lettered_job_ids: tuple[JobId, ...] = ()
    skipped_job_ids: tuple[JobId, ...] = ()


@dataclass(frozen=True, slots=True)
class _StaleLeasedJob:
    id: JobId
    attempts: int
    max_attempts: int
    lease_owner: str | None
    lease_expires_at: datetime | None


@dataclass(frozen=True, slots=True)
class _ClaimedJob:
    id: JobId
    job_type: JobType
    payload: JobPayload
    attempt: int
    max_attempts: int


class JobWorkerService:
    """Business workflow for worker-side job execution.

    The worker service coordinates stale lease recovery, queue polling,
    PostgreSQL state transitions, and safe built-in handler execution. It never
    executes arbitrary commands, scripts, containers, subprocesses, or
    user-provided code strings. Duplicate Redis messages are safe because every
    dispatch signal must claim the
    PostgreSQL row before any handler runs.
    """

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        queue: JobQueue,
        worker_id: str,
        lease_seconds: float,
        handler_runner: JobHandlerRunner = run_job_handler,
        logger: logging.Logger | None = None,
    ) -> None:
        if not worker_id:
            raise ValueError("worker_id must not be empty")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be greater than 0")
        self._session_factory = session_factory
        self._queue = queue
        self._worker_id = worker_id
        self._lease_seconds = lease_seconds
        self._handler_runner = handler_runner
        self._logger = logger or logging.getLogger(__name__)

    async def recover_stale_jobs(
        self,
        *,
        as_of: datetime | None = None,
        limit: int = DEFAULT_STALE_RECOVERY_LIMIT,
    ) -> StaleJobRecoveryResult:
        """Recover running jobs whose leases have expired.

        The current attempt was already counted when the job was claimed. Stale
        jobs with attempts remaining are requeued and receive a fresh Redis
        dispatch signal after the database transaction commits. Stale jobs that
        have exhausted ``max_attempts`` are moved to ``dead_lettered``.
        """

        if limit < 1:
            raise ValueError("limit must be greater than or equal to 1")

        cutoff = as_of or datetime.now(UTC)
        requeued_job_ids: list[JobId] = []
        dead_lettered_job_ids: list[JobId] = []
        skipped_job_ids: list[JobId] = []

        async with session_scope(self._session_factory) as session:
            repository = JobRepository(session)
            stale_rows = await repository.find_stale_leased_jobs(
                as_of=cutoff,
                limit=limit,
            )
            stale_jobs = tuple(_snapshot_stale_leased_job(job) for job in stale_rows)

        for stale_job in stale_jobs:
            error_message = _stale_lease_error_message(
                job=stale_job,
                recovered_at=cutoff,
            )
            if stale_job.attempts < stale_job.max_attempts:
                stored_status = await self._record_retry(stale_job.id, error_message)
                if stored_status is None:
                    skipped_job_ids.append(stale_job.id)
                else:
                    requeued_job_ids.append(stale_job.id)
            else:
                stored_status = await self._record_dead_letter(
                    stale_job.id,
                    error_message,
                )
                if stored_status is None:
                    skipped_job_ids.append(stale_job.id)
                else:
                    dead_lettered_job_ids.append(stale_job.id)

        for job_id in requeued_job_ids:
            await self._queue.enqueue(job_id)

        result = StaleJobRecoveryResult(
            scanned=len(stale_jobs),
            requeued_job_ids=tuple(requeued_job_ids),
            dead_lettered_job_ids=tuple(dead_lettered_job_ids),
            skipped_job_ids=tuple(skipped_job_ids),
        )
        if result.scanned > 0:
            self._logger.warning(
                "stale job leases recovered",
                extra={
                    "worker_id": self._worker_id,
                    "stale_jobs_scanned": result.scanned,
                    "stale_jobs_requeued": len(result.requeued_job_ids),
                    "stale_jobs_dead_lettered": len(result.dead_lettered_job_ids),
                    "stale_jobs_skipped": len(result.skipped_job_ids),
                },
            )
        return result

    async def process_one_job(
        self,
        *,
        timeout_seconds: float | None = None,
    ) -> WorkerProcessResult:
        """Poll for one job ID, claim it, execute it, and persist the outcome."""

        job_id = await self._queue.dequeue(timeout_seconds=timeout_seconds)
        if job_id is None:
            return WorkerProcessResult(outcome=WorkerProcessOutcome.NO_MESSAGE)

        self._logger.info(
            "job dispatch signal received",
            extra={"worker_id": self._worker_id, "job_id": str(job_id)},
        )
        claimed_job = await self._claim_job(job_id)
        if claimed_job is None:
            await self._queue.acknowledge(job_id)
            current_status = await self._get_job_status(job_id)
            if current_status is JobStatus.CANCELLED:
                self._logger.info(
                    "cancelled job dispatch signal skipped",
                    extra={
                        "worker_id": self._worker_id,
                        "job_id": str(job_id),
                        "worker_outcome": WorkerProcessOutcome.CANCELLED.value,
                    },
                )
                return WorkerProcessResult(
                    outcome=WorkerProcessOutcome.CANCELLED,
                    job_id=job_id,
                    job_status=JobStatus.CANCELLED,
                )

            self._logger.info(
                "job claim skipped",
                extra={
                    "worker_id": self._worker_id,
                    "job_id": str(job_id),
                    "worker_outcome": WorkerProcessOutcome.CLAIM_SKIPPED.value,
                },
            )
            return WorkerProcessResult(
                outcome=WorkerProcessOutcome.CLAIM_SKIPPED,
                job_id=job_id,
                job_status=current_status,
            )

        self._logger.info(
            "job started",
            extra={
                "worker_id": self._worker_id,
                "job_id": str(claimed_job.id),
                "job_type": claimed_job.job_type.value,
                "attempt": claimed_job.attempt,
            },
        )

        cancellation_result = await self._record_cancelled_if_requested(claimed_job)
        if cancellation_result is not None:
            return cancellation_result

        try:
            result = await self._handler_runner(
                claimed_job.job_type,
                claimed_job.payload,
                context=JobHandlerContext(
                    attempt=claimed_job.attempt,
                    job_id=claimed_job.id,
                    cancellation_check=self._cancellation_check_for(claimed_job.id),
                ),
            )
        except JobCancellationRequestedError as exc:
            return await self._record_cancelled_job(claimed_job, exc)
        except JobHandlerError as exc:
            return await self._record_failed_job(claimed_job, exc)
        except Exception as exc:
            self._logger.exception(
                "job handler raised unexpected exception",
                extra={
                    "worker_id": self._worker_id,
                    "job_id": str(claimed_job.id),
                    "job_type": claimed_job.job_type.value,
                    "attempt": claimed_job.attempt,
                },
            )
            return await self._record_failed_job(claimed_job, exc)

        cancellation_result = await self._record_cancelled_if_requested(claimed_job)
        if cancellation_result is not None:
            return cancellation_result

        stored_status = await self._record_success(claimed_job.id, result)
        if stored_status is None:
            cancellation_result = await self._record_cancelled_if_requested(claimed_job)
            if cancellation_result is not None:
                return cancellation_result
            await self._queue.acknowledge(claimed_job.id)
            self._logger.warning(
                "job completion skipped because status was no longer running",
                extra={
                    "worker_id": self._worker_id,
                    "job_id": str(claimed_job.id),
                    "worker_outcome": WorkerProcessOutcome.RECORD_SKIPPED.value,
                },
            )
            return WorkerProcessResult(
                outcome=WorkerProcessOutcome.RECORD_SKIPPED,
                job_id=claimed_job.id,
            )

        await self._queue.acknowledge(claimed_job.id)

        self._logger.info(
            "job succeeded",
            extra={
                "worker_id": self._worker_id,
                "job_id": str(claimed_job.id),
                "job_type": claimed_job.job_type.value,
                "attempt": claimed_job.attempt,
                "worker_outcome": WorkerProcessOutcome.SUCCEEDED.value,
            },
        )
        return WorkerProcessResult(
            outcome=WorkerProcessOutcome.SUCCEEDED,
            job_id=claimed_job.id,
            job_status=stored_status,
        )

    async def _claim_job(self, job_id: JobId) -> _ClaimedJob | None:
        lease_expires_at = datetime.now(UTC) + timedelta(seconds=self._lease_seconds)
        async with session_scope(self._session_factory) as session:
            repository = JobRepository(session)
            job = await repository.claim_queued_job(
                job_id=job_id,
                worker_id=self._worker_id,
                lease_expires_at=lease_expires_at,
            )
            if job is None:
                return None
            return _snapshot_claimed_job(job)

    async def _record_success(
        self,
        job_id: JobId,
        result: JobResult,
    ) -> JobStatus | None:
        async with session_scope(self._session_factory) as session:
            repository = JobRepository(session)
            completed = await repository.complete_job(job_id=job_id, result=result)
            if completed is None:
                return None
            return JobStatus(completed.status)

    async def _record_cancelled_if_requested(
        self,
        claimed_job: _ClaimedJob,
    ) -> WorkerProcessResult | None:
        if not await self._is_cancellation_requested(claimed_job.id):
            return None
        exc = JobCancellationRequestedError("job cancellation requested")
        return await self._record_cancelled_job(claimed_job, exc)

    async def _record_cancelled_job(
        self,
        claimed_job: _ClaimedJob,
        exc: Exception,
    ) -> WorkerProcessResult:
        error_message = _safe_error_message(exc)
        stored_status = await self._record_cancelled(claimed_job.id, error_message)
        await self._queue.acknowledge(claimed_job.id)
        if stored_status is None:
            self._logger.warning(
                "job cancellation recording skipped because status was not cancellable",
                extra={
                    "worker_id": self._worker_id,
                    "job_id": str(claimed_job.id),
                    "worker_outcome": WorkerProcessOutcome.RECORD_SKIPPED.value,
                    "error_type": exc.__class__.__name__,
                },
            )
            return WorkerProcessResult(
                outcome=WorkerProcessOutcome.RECORD_SKIPPED,
                job_id=claimed_job.id,
                error_message=error_message,
            )

        self._logger.info(
            "job cancelled",
            extra={
                "worker_id": self._worker_id,
                "job_id": str(claimed_job.id),
                "job_type": claimed_job.job_type.value,
                "attempt": claimed_job.attempt,
                "worker_outcome": WorkerProcessOutcome.CANCELLED.value,
                "error_type": exc.__class__.__name__,
            },
        )
        return WorkerProcessResult(
            outcome=WorkerProcessOutcome.CANCELLED,
            job_id=claimed_job.id,
            job_status=stored_status,
            error_message=error_message,
        )

    async def _record_failed_job(
        self,
        claimed_job: _ClaimedJob,
        exc: Exception,
    ) -> WorkerProcessResult:
        cancellation_result = await self._record_cancelled_if_requested(claimed_job)
        if cancellation_result is not None:
            return cancellation_result

        error_message = _safe_error_message(exc)
        attempts_remaining = claimed_job.attempt < claimed_job.max_attempts
        if attempts_remaining:
            stored_status = await self._record_retry(claimed_job.id, error_message)
            if stored_status is not None:
                await self._queue.enqueue(claimed_job.id)
            outcome = WorkerProcessOutcome.RETRIED
            log_message = "job failed; retry scheduled"
        else:
            stored_status = await self._record_dead_letter(
                claimed_job.id,
                error_message,
            )
            outcome = WorkerProcessOutcome.DEAD_LETTERED
            log_message = "job dead-lettered after exhausting attempts"

        if stored_status is None:
            cancellation_result = await self._record_cancelled_if_requested(claimed_job)
            if cancellation_result is not None:
                return cancellation_result
            await self._queue.acknowledge(claimed_job.id)
            self._logger.warning(
                "job failure recording skipped because status was no longer running",
                extra={
                    "worker_id": self._worker_id,
                    "job_id": str(claimed_job.id),
                    "worker_outcome": WorkerProcessOutcome.RECORD_SKIPPED.value,
                    "error_type": exc.__class__.__name__,
                },
            )
            return WorkerProcessResult(
                outcome=WorkerProcessOutcome.RECORD_SKIPPED,
                job_id=claimed_job.id,
                error_message=error_message,
            )

        await self._queue.acknowledge(claimed_job.id)

        self._logger.warning(
            log_message,
            extra={
                "worker_id": self._worker_id,
                "job_id": str(claimed_job.id),
                "job_type": claimed_job.job_type.value,
                "attempt": claimed_job.attempt,
                "max_attempts": claimed_job.max_attempts,
                "worker_outcome": outcome.value,
                "error_type": exc.__class__.__name__,
            },
        )
        return WorkerProcessResult(
            outcome=outcome,
            job_id=claimed_job.id,
            job_status=stored_status,
            error_message=error_message,
        )

    async def _record_retry(
        self,
        job_id: JobId,
        error_message: str,
    ) -> JobStatus | None:
        async with session_scope(self._session_factory) as session:
            repository = JobRepository(session)
            requeued = await repository.requeue_job(
                job_id=job_id,
                error_message=error_message,
            )
            if requeued is None:
                return None
            return JobStatus(requeued.status)

    async def _record_dead_letter(
        self,
        job_id: JobId,
        error_message: str,
    ) -> JobStatus | None:
        async with session_scope(self._session_factory) as session:
            repository = JobRepository(session)
            dead_lettered = await repository.mark_dead_lettered(
                job_id=job_id,
                error_message=error_message,
            )
            if dead_lettered is None:
                return None
            return JobStatus(dead_lettered.status)

    async def _record_cancelled(
        self,
        job_id: JobId,
        error_message: str,
    ) -> JobStatus | None:
        async with session_scope(self._session_factory) as session:
            repository = JobRepository(session)
            cancelled = await repository.mark_cancelled(
                job_id=job_id,
                worker_id=self._worker_id,
                error_message=error_message,
            )
            if cancelled is None:
                return None
            return JobStatus(cancelled.status)

    async def _get_job_status(self, job_id: JobId) -> JobStatus | None:
        async with session_scope(self._session_factory) as session:
            repository = JobRepository(session)
            job = await repository.get_job_by_id(job_id)
            if job is None:
                return None
            return JobStatus(job.status)

    async def _is_cancellation_requested(self, job_id: JobId) -> bool:
        async with session_scope(self._session_factory) as session:
            repository = JobRepository(session)
            job = await repository.get_job_by_id(job_id)
            if job is None:
                return False
            status = JobStatus(job.status)
            if status is JobStatus.CANCELLED:
                return True
            if status is not JobStatus.CANCEL_REQUESTED:
                return False
            return job.lease_owner in {None, self._worker_id}

    def _cancellation_check_for(self, job_id: JobId) -> CancellationCheck:
        async def cancellation_check() -> bool:
            return await self._is_cancellation_requested(job_id)

        return cancellation_check


def _snapshot_stale_leased_job(job: JobModel) -> _StaleLeasedJob:
    return _StaleLeasedJob(
        id=job.id,
        attempts=job.attempts,
        max_attempts=job.max_attempts,
        lease_owner=job.lease_owner,
        lease_expires_at=job.lease_expires_at,
    )


def _snapshot_claimed_job(job: JobModel) -> _ClaimedJob:
    return _ClaimedJob(
        id=job.id,
        job_type=JobType(job.job_type),
        payload=dict(job.payload),
        attempt=job.attempts,
        max_attempts=job.max_attempts,
    )


def _safe_error_message(exc: Exception) -> str:
    raw_message = str(exc).strip() or exc.__class__.__name__
    message = f"{exc.__class__.__name__}: {raw_message}"
    return message[:MAX_RECORDED_ERROR_MESSAGE_LENGTH]


def _stale_lease_error_message(
    *,
    job: _StaleLeasedJob,
    recovered_at: datetime,
) -> str:
    lease_owner = job.lease_owner or "unknown"
    if job.lease_expires_at is None:
        lease_expires_at = "unknown"
    else:
        lease_expires_at = job.lease_expires_at.isoformat()
    message = (
        "StaleLeaseRecovery: job lease expired at "
        f"{lease_expires_at} for worker {lease_owner}; "
        f"recovered at {recovered_at.isoformat()}"
    )
    return message[:MAX_RECORDED_ERROR_MESSAGE_LENGTH]
