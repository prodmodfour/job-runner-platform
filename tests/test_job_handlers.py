from __future__ import annotations

import asyncio
import hashlib

import pytest

from job_runner_platform.domain.jobs import ALLOWED_JOB_TYPES, JobType
from job_runner_platform.handlers import (
    BUILTIN_JOB_HANDLERS,
    MAX_SLEEP_SECONDS,
    HandlerExecutionError,
    InvalidJobPayloadError,
    JobHandlerContext,
    UnknownJobHandlerError,
    run_job_handler,
)


def test_builtin_handler_registry_covers_domain_allowlist() -> None:
    assert set(BUILTIN_JOB_HANDLERS) == set(ALLOWED_JOB_TYPES)


def test_echo_handler_returns_json_payload_copy() -> None:
    payload = {"message": "hello", "nested": {"count": 1}}

    result = asyncio.run(run_job_handler(JobType.ECHO, payload))
    payload["nested"] = {"count": 2}

    assert result == {"payload": {"message": "hello", "nested": {"count": 1}}}


def test_sleep_handler_sleeps_for_bounded_duration() -> None:
    result = asyncio.run(run_job_handler(JobType.SLEEP, {"seconds": 0}))

    assert result == {"slept_seconds": 0.0}


def test_sleep_handler_rejects_duration_above_demo_limit() -> None:
    with pytest.raises(InvalidJobPayloadError, match="invalid payload for sleep"):
        asyncio.run(
            run_job_handler(JobType.SLEEP, {"seconds": MAX_SLEEP_SECONDS + 0.1})
        )


def test_checksum_handler_returns_sha256_for_utf8_text() -> None:
    result = asyncio.run(run_job_handler(JobType.CHECKSUM, {"text": "hello"}))

    assert result == {
        "algorithm": "sha256",
        "encoding": "utf-8",
        "checksum": hashlib.sha256(b"hello").hexdigest(),
        "byte_length": 5,
    }


def test_fail_once_handler_fails_first_attempt_then_succeeds() -> None:
    with pytest.raises(HandlerExecutionError, match="first attempt"):
        asyncio.run(
            run_job_handler(
                JobType.FAIL_ONCE,
                {},
                context=JobHandlerContext(attempt=1),
            )
        )

    result = asyncio.run(
        run_job_handler(
            JobType.FAIL_ONCE,
            {},
            context=JobHandlerContext(attempt=2),
        )
    )

    assert result == {"failed_once": True, "attempt": 2}


def test_always_fail_handler_raises_safe_execution_error() -> None:
    with pytest.raises(HandlerExecutionError, match="always_fail intentionally failed"):
        asyncio.run(run_job_handler(JobType.ALWAYS_FAIL, {}))


def test_handler_context_rejects_invalid_attempt_number() -> None:
    with pytest.raises(ValueError, match="attempt"):
        JobHandlerContext(attempt=0)


def test_unknown_handler_name_is_rejected() -> None:
    with pytest.raises(UnknownJobHandlerError, match="not an allowlisted"):
        asyncio.run(run_job_handler("command", {}))


def test_handlers_reject_non_json_payload_values() -> None:
    with pytest.raises(InvalidJobPayloadError, match="JSON serializable"):
        asyncio.run(run_job_handler(JobType.ECHO, {"value": object()}))
