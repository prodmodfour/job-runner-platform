from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Final
from uuid import UUID

from pydantic import AwareDatetime, Field


class JobType(StrEnum):
    """Safe allowlisted demo job handlers.

    The platform intentionally supports only built-in handlers. These values are
    names, not shell commands, scripts, containers, or user-provided code.
    """

    ECHO = "echo"
    SLEEP = "sleep"
    CHECKSUM = "checksum"
    FAIL_ONCE = "fail_once"
    ALWAYS_FAIL = "always_fail"


class JobStatus(StrEnum):
    """Explicit lifecycle states for a job."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    DEAD_LETTERED = "dead_lettered"


type JobId = UUID
type JobPayload = dict[str, Any]
type JobResult = dict[str, Any]
type JobAttempts = Annotated[int, Field(ge=0)]
type MaxAttempts = Annotated[int, Field(ge=1, le=25)]
type JobPriority = Annotated[int, Field(ge=-100, le=100)]
type ErrorMessage = Annotated[str, Field(min_length=1, max_length=2048)]
type IdempotencyKey = Annotated[
    str,
    Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"),
]
type JobTimestamp = AwareDatetime
type LeaseOwner = Annotated[str, Field(min_length=1, max_length=128)]
type LeaseExpiry = AwareDatetime

ALLOWED_JOB_TYPES: Final[frozenset[JobType]] = frozenset(JobType)
TERMINAL_JOB_STATUSES: Final[frozenset[JobStatus]] = frozenset(
    {
        JobStatus.SUCCEEDED,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
        JobStatus.DEAD_LETTERED,
    }
)
DEFAULT_MAX_ATTEMPTS: Final[int] = 3
DEFAULT_JOB_PRIORITY: Final[int] = 0


def is_terminal_status(status: JobStatus) -> bool:
    """Return whether a status represents a terminal lifecycle state."""

    return status in TERMINAL_JOB_STATUSES
