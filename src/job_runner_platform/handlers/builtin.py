from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Literal, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from job_runner_platform.domain.jobs import (
    ALLOWED_JOB_TYPES,
    JobId,
    JobPayload,
    JobResult,
    JobType,
)

MAX_SLEEP_SECONDS: Final[float] = 5.0
MAX_CHECKSUM_TEXT_BYTES: Final[int] = 1_000_000


@dataclass(frozen=True, slots=True)
class JobHandlerContext:
    """Execution metadata passed to a safe built-in job handler."""

    attempt: int = 1
    job_id: JobId | None = None

    def __post_init__(self) -> None:
        if self.attempt < 1:
            raise ValueError("attempt must be greater than or equal to 1")


class JobHandler(Protocol):
    """Protocol implemented by safe allowlisted job handlers."""

    async def __call__(
        self,
        payload: JobPayload,
        context: JobHandlerContext,
    ) -> JobResult:
        """Execute a built-in handler and return a JSON-safe result."""


class JobHandlerError(Exception):
    """Base class for safe job handler failures."""


class UnknownJobHandlerError(JobHandlerError):
    """Raised when no built-in handler exists for the requested job type."""


class InvalidJobPayloadError(JobHandlerError):
    """Raised when a handler payload does not match its documented shape."""


class HandlerExecutionError(JobHandlerError):
    """Raised by handlers that intentionally fail for retry/dead-letter demos."""


class _HandlerPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class _SleepPayload(_HandlerPayload):
    seconds: float = Field(ge=0.0, le=MAX_SLEEP_SECONDS)

    @field_validator("seconds", mode="before")
    @classmethod
    def seconds_must_be_number(cls, value: object) -> object:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError("seconds must be a number")
        return value


class _ChecksumPayload(_HandlerPayload):
    text: str
    algorithm: Literal["sha256"] = "sha256"

    @field_validator("text", mode="before")
    @classmethod
    def text_must_be_string(cls, value: object) -> object:
        if not isinstance(value, str):
            raise ValueError("text must be a string")
        return value

    @field_validator("text")
    @classmethod
    def text_must_fit_demo_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > MAX_CHECKSUM_TEXT_BYTES:
            raise ValueError("text exceeds the checksum demo size limit")
        return value


class _EmptyPayload(_HandlerPayload):
    pass


async def echo_handler(
    payload: JobPayload,
    context: JobHandlerContext,
) -> JobResult:
    """Return the submitted JSON object without running external code."""

    _ = context
    return {"payload": _clone_json_object(payload)}


async def sleep_handler(
    payload: JobPayload,
    context: JobHandlerContext,
) -> JobResult:
    """Sleep for a bounded number of seconds using asyncio only."""

    _ = context
    parsed_payload = _validate_payload(JobType.SLEEP, _SleepPayload, payload)
    await asyncio.sleep(parsed_payload.seconds)
    return {"slept_seconds": parsed_payload.seconds}


async def checksum_handler(
    payload: JobPayload,
    context: JobHandlerContext,
) -> JobResult:
    """Compute a deterministic SHA-256 checksum for provided text."""

    _ = context
    parsed_payload = _validate_payload(JobType.CHECKSUM, _ChecksumPayload, payload)
    encoded_text = parsed_payload.text.encode("utf-8")
    digest = hashlib.sha256(encoded_text).hexdigest()
    return {
        "algorithm": parsed_payload.algorithm,
        "encoding": "utf-8",
        "checksum": digest,
        "byte_length": len(encoded_text),
    }


async def fail_once_handler(
    payload: JobPayload,
    context: JobHandlerContext,
) -> JobResult:
    """Fail on the first attempt and succeed on subsequent attempts."""

    _validate_payload(JobType.FAIL_ONCE, _EmptyPayload, payload)
    if context.attempt == 1:
        raise HandlerExecutionError("fail_once intentionally failed on first attempt")
    await asyncio.sleep(0)
    return {"failed_once": True, "attempt": context.attempt}


async def always_fail_handler(
    payload: JobPayload,
    context: JobHandlerContext,
) -> JobResult:
    """Always fail safely for retry and dead-letter demonstrations."""

    _ = context
    _validate_payload(JobType.ALWAYS_FAIL, _EmptyPayload, payload)
    await asyncio.sleep(0)
    raise HandlerExecutionError("always_fail intentionally failed")


_BUILTIN_JOB_HANDLERS: Final[dict[JobType, JobHandler]] = {
    JobType.ECHO: echo_handler,
    JobType.SLEEP: sleep_handler,
    JobType.CHECKSUM: checksum_handler,
    JobType.FAIL_ONCE: fail_once_handler,
    JobType.ALWAYS_FAIL: always_fail_handler,
}
BUILTIN_JOB_HANDLERS: Final[Mapping[JobType, JobHandler]] = MappingProxyType(
    _BUILTIN_JOB_HANDLERS,
)


async def run_job_handler(
    job_type: JobType | str,
    payload: JobPayload | None = None,
    *,
    context: JobHandlerContext | None = None,
) -> JobResult:
    """Run a safe built-in handler for an allowlisted job type."""

    handler = get_job_handler(job_type)
    resolved_payload = dict(payload or {})
    resolved_context = context if context is not None else JobHandlerContext()
    return await handler(resolved_payload, resolved_context)


def get_job_handler(job_type: JobType | str) -> JobHandler:
    """Return the built-in handler for a safe allowlisted job type."""

    normalized_job_type = _normalize_job_type(job_type)
    try:
        return BUILTIN_JOB_HANDLERS[normalized_job_type]
    except KeyError as exc:
        message = (
            f"no built-in handler registered for job_type {normalized_job_type.value!r}"
        )
        raise UnknownJobHandlerError(message) from exc


def _normalize_job_type(job_type: JobType | str) -> JobType:
    if isinstance(job_type, JobType):
        normalized_job_type = job_type
    else:
        try:
            normalized_job_type = JobType(job_type)
        except ValueError as exc:
            message = f"job_type {job_type!r} is not an allowlisted built-in handler"
            raise UnknownJobHandlerError(message) from exc

    if normalized_job_type not in ALLOWED_JOB_TYPES:
        message = f"job_type {normalized_job_type.value!r} is not allowlisted"
        raise UnknownJobHandlerError(message)
    return normalized_job_type


def _validate_payload[PayloadModelT: BaseModel](
    job_type: JobType,
    model_type: type[PayloadModelT],
    payload: JobPayload,
) -> PayloadModelT:
    _ensure_json_object(payload)
    try:
        return model_type.model_validate(payload)
    except ValidationError as exc:
        message = f"invalid payload for {job_type.value} handler"
        raise InvalidJobPayloadError(message) from exc


def _clone_json_object(payload: JobPayload) -> JobPayload:
    _ensure_json_object(payload)
    serialized_payload = json.dumps(payload, sort_keys=True)
    cloned_payload = json.loads(serialized_payload)
    return cast(JobPayload, cloned_payload)


def _ensure_json_object(payload: JobPayload) -> None:
    if not all(isinstance(key, str) for key in payload):
        raise InvalidJobPayloadError("handler payload keys must be strings")
    try:
        json.dumps(payload)
    except (TypeError, ValueError) as exc:
        message = "handler payload must be JSON serializable"
        raise InvalidJobPayloadError(message) from exc


_registered_job_types = frozenset(BUILTIN_JOB_HANDLERS)
if _registered_job_types != ALLOWED_JOB_TYPES:
    missing = sorted(
        job_type.value for job_type in ALLOWED_JOB_TYPES - _registered_job_types
    )
    extra = sorted(
        job_type.value for job_type in _registered_job_types - ALLOWED_JOB_TYPES
    )
    message = f"built-in handler registry mismatch; missing={missing}, extra={extra}"
    raise RuntimeError(message)
