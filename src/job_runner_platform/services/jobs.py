from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from job_runner_platform.database.models import JobModel
from job_runner_platform.domain.jobs import (
    ALLOWED_JOB_TYPES,
    DEFAULT_JOB_PRIORITY,
    DEFAULT_MAX_ATTEMPTS,
    IdempotencyKey,
    JobId,
    JobPayload,
    JobPriority,
    JobStatus,
    JobType,
    MaxAttempts,
    is_terminal_status,
)
from job_runner_platform.queues import JobQueue
from job_runner_platform.repositories import JobRepository

DEFAULT_LIST_LIMIT: Final[int] = 50
MAX_LIST_LIMIT: Final[int] = 100


@dataclass(frozen=True, slots=True)
class JobCreationResult:
    """Result for a create-job service call."""

    job: JobModel
    idempotency_replayed: bool


@dataclass(frozen=True, slots=True)
class JobListResult:
    """Stable page of jobs returned by the service layer."""

    items: tuple[JobModel, ...]
    count: int
    limit: int
    offset: int


@dataclass(frozen=True, slots=True)
class JobCancellationResult:
    """Result for an accepted cancellation request."""

    job: JobModel
    cancellation_requested: bool
    message: str


class JobServiceError(Exception):
    """Base class for job service failures that API routes can map later."""


class InvalidJobTypeError(JobServiceError):
    """Raised when a requested job type is not an allowlisted demo handler."""


class InvalidJobStatusError(JobServiceError):
    """Raised when a status filter cannot be interpreted safely."""


class InvalidPaginationError(JobServiceError):
    """Raised when list pagination parameters are outside supported bounds."""


class JobNotFoundError(JobServiceError):
    """Raised when a job-specific operation targets an unknown job ID."""


class JobCancellationConflictError(JobServiceError):
    """Raised when a job is already terminal and cannot be cancelled."""


class JobService:
    """Business workflow layer for jobs.

    The service coordinates repository persistence with queue dispatch signals.
    PostgreSQL remains the source of truth and Redis remains only a wake-up
    signal. The service validates that submitted job types are one of the safe
    built-in demo handlers; it never executes user-provided commands, scripts,
    containers, subprocesses, or code strings.
    """

    def __init__(self, *, repository: JobRepository, queue: JobQueue) -> None:
        self._repository = repository
        self._queue = queue

    async def create_job(
        self,
        *,
        job_type: JobType | str,
        payload: JobPayload | None = None,
        priority: JobPriority = DEFAULT_JOB_PRIORITY,
        max_attempts: MaxAttempts = DEFAULT_MAX_ATTEMPTS,
        idempotency_key: IdempotencyKey | None = None,
    ) -> JobCreationResult:
        """Create a queued job and publish one dispatch signal.

        If an idempotency key is supplied and already exists, the existing job
        is returned without creating another database row or queue signal.
        """

        validated_job_type = _normalize_job_type(job_type)
        if idempotency_key is not None:
            existing_job = await self._repository.find_by_idempotency_key(
                idempotency_key,
            )
            if existing_job is not None:
                return JobCreationResult(
                    job=existing_job,
                    idempotency_replayed=True,
                )

        job = await self._repository.create_job(
            job_type=validated_job_type,
            payload=payload,
            priority=priority,
            max_attempts=max_attempts,
            idempotency_key=idempotency_key,
        )
        await self._queue.enqueue(job.id)
        return JobCreationResult(job=job, idempotency_replayed=False)

    async def get_job(self, job_id: JobId) -> JobModel | None:
        """Return a job by ID, if it exists."""

        return await self._repository.get_job_by_id(job_id)

    async def list_jobs(
        self,
        *,
        limit: int = DEFAULT_LIST_LIMIT,
        offset: int = 0,
        status: JobStatus | str | None = None,
    ) -> JobListResult:
        """Return a validated page of jobs with an optional status filter."""

        _validate_pagination(limit=limit, offset=offset)
        validated_status = _normalize_status(status)
        jobs = await self._repository.list_jobs(
            limit=limit,
            offset=offset,
            status=validated_status,
        )
        items = tuple(jobs)
        return JobListResult(
            items=items,
            count=len(items),
            limit=limit,
            offset=offset,
        )

    async def cancel_job(self, job_id: JobId) -> JobCancellationResult:
        """Cancel a queued job or request cancellation for a running job.

        Queued jobs move directly to ``cancelled`` because no worker has started
        them. Running jobs move to ``cancel_requested`` so later worker runtime
        code can cooperate safely. Terminal jobs are rejected with a conflict.
        """

        existing_job = await self._repository.get_job_by_id(job_id)
        if existing_job is None:
            raise JobNotFoundError(f"job {job_id} was not found")

        existing_status = _job_status(existing_job)
        if is_terminal_status(existing_status):
            raise JobCancellationConflictError(
                f"job {job_id} is already terminal with status {existing_status.value}",
            )
        if existing_status is JobStatus.CANCEL_REQUESTED:
            return JobCancellationResult(
                job=existing_job,
                cancellation_requested=True,
                message="cancellation already requested",
            )

        updated_job = await self._repository.request_cancellation(job_id)
        if updated_job is None:
            raise JobNotFoundError(f"job {job_id} was not found")

        updated_status = _job_status(updated_job)
        if updated_status is JobStatus.CANCELLED:
            message = "queued job cancelled"
        elif updated_status is JobStatus.CANCEL_REQUESTED:
            message = "cancellation requested"
        else:
            message = "job is not cancellable in its current state"
            raise JobCancellationConflictError(message)

        return JobCancellationResult(
            job=updated_job,
            cancellation_requested=True,
            message=message,
        )


def _normalize_job_type(job_type: JobType | str) -> JobType:
    if isinstance(job_type, JobType):
        normalized = job_type
    else:
        try:
            normalized = JobType(job_type)
        except ValueError as exc:
            allowed = _allowed_job_types_message()
            message = f"job_type must be one of the allowlisted handlers: {allowed}"
            raise InvalidJobTypeError(message) from exc

    if normalized not in ALLOWED_JOB_TYPES:
        allowed = _allowed_job_types_message()
        message = f"job_type must be one of the allowlisted handlers: {allowed}"
        raise InvalidJobTypeError(message)
    return normalized


def _allowed_job_types_message() -> str:
    return ", ".join(sorted(job_type.value for job_type in ALLOWED_JOB_TYPES))


def _normalize_status(status: JobStatus | str | None) -> JobStatus | None:
    if status is None:
        return None
    if isinstance(status, JobStatus):
        return status
    try:
        return JobStatus(status)
    except ValueError as exc:
        allowed = ", ".join(status.value for status in JobStatus)
        message = f"status must be one of: {allowed}"
        raise InvalidJobStatusError(message) from exc


def _validate_pagination(*, limit: int, offset: int) -> None:
    if limit < 1 or limit > MAX_LIST_LIMIT:
        message = f"limit must be between 1 and {MAX_LIST_LIMIT}"
        raise InvalidPaginationError(message)
    if offset < 0:
        raise InvalidPaginationError("offset must be greater than or equal to 0")


def _job_status(job: JobModel) -> JobStatus:
    return JobStatus(job.status)
