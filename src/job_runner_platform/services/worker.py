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
    JobHandlerContext,
    JobHandlerError,
    run_job_handler,
)
from job_runner_platform.queues import JobQueue
from job_runner_platform.repositories import JobRepository

MAX_RECORDED_ERROR_MESSAGE_LENGTH: Final[int] = 2048


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
    FAILED = "failed"
    RECORD_SKIPPED = "record_skipped"


@dataclass(frozen=True, slots=True)
class WorkerProcessResult:
    """Result from processing at most one queued dispatch signal."""

    outcome: WorkerProcessOutcome
    job_id: JobId | None = None
    job_status: JobStatus | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class _ClaimedJob:
    id: JobId
    job_type: JobType
    payload: JobPayload
    attempt: int


class JobWorkerService:
    """Business workflow for worker-side job execution.

    The worker service coordinates queue polling, PostgreSQL state transitions,
    and safe built-in handler execution. It never executes arbitrary commands,
    scripts, containers, subprocesses, or user-provided code strings. Duplicate
    Redis messages are safe because every dispatch signal must claim the
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

        try:
            result = await self._handler_runner(
                claimed_job.job_type,
                claimed_job.payload,
                context=JobHandlerContext(
                    attempt=claimed_job.attempt,
                    job_id=claimed_job.id,
                ),
            )
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

        stored_status = await self._record_success(claimed_job.id, result)
        await self._queue.acknowledge(claimed_job.id)
        if stored_status is None:
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

    async def _record_failed_job(
        self,
        claimed_job: _ClaimedJob,
        exc: Exception,
    ) -> WorkerProcessResult:
        error_message = _safe_error_message(exc)
        stored_status = await self._record_failure(claimed_job.id, error_message)
        await self._queue.acknowledge(claimed_job.id)
        if stored_status is None:
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

        self._logger.warning(
            "job failed",
            extra={
                "worker_id": self._worker_id,
                "job_id": str(claimed_job.id),
                "job_type": claimed_job.job_type.value,
                "attempt": claimed_job.attempt,
                "worker_outcome": WorkerProcessOutcome.FAILED.value,
                "error_type": exc.__class__.__name__,
            },
        )
        return WorkerProcessResult(
            outcome=WorkerProcessOutcome.FAILED,
            job_id=claimed_job.id,
            job_status=stored_status,
            error_message=error_message,
        )

    async def _record_failure(
        self,
        job_id: JobId,
        error_message: str,
    ) -> JobStatus | None:
        async with session_scope(self._session_factory) as session:
            repository = JobRepository(session)
            failed = await repository.fail_job(
                job_id=job_id,
                error_message=error_message,
            )
            if failed is None:
                return None
            return JobStatus(failed.status)


def _snapshot_claimed_job(job: JobModel) -> _ClaimedJob:
    return _ClaimedJob(
        id=job.id,
        job_type=JobType(job.job_type),
        payload=dict(job.payload),
        attempt=job.attempts,
    )


def _safe_error_message(exc: Exception) -> str:
    raw_message = str(exc).strip() or exc.__class__.__name__
    message = f"{exc.__class__.__name__}: {raw_message}"
    return message[:MAX_RECORDED_ERROR_MESSAGE_LENGTH]
