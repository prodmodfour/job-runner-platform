from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from job_runner_platform.api.schemas import (
    CancellationResponse,
    CreateJobRequest,
    CreateJobResponse,
    JobDetailResponse,
    JobListResponse,
)
from job_runner_platform.domain.jobs import (
    DEFAULT_JOB_PRIORITY,
    DEFAULT_MAX_ATTEMPTS,
    JobStatus,
    JobType,
    is_terminal_status,
)


def _job_detail_response() -> JobDetailResponse:
    now = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    return JobDetailResponse.model_validate(
        {
            "id": uuid4(),
            "job_type": "echo",
            "status": "queued",
            "priority": 0,
            "attempts": 0,
            "max_attempts": 3,
            "payload": {"message": "hello"},
            "result": None,
            "error_message": None,
            "idempotency_key": "demo-key-001",
            "created_at": now,
            "updated_at": now,
            "queued_at": now,
            "started_at": None,
            "finished_at": None,
            "lease_owner": None,
            "lease_expires_at": None,
        }
    )


def test_create_job_request_accepts_allowlisted_job_type() -> None:
    request = CreateJobRequest.model_validate(
        {
            "job_type": "echo",
            "payload": {"message": "hello"},
            "idempotency_key": "demo-key-001",
        }
    )

    assert request.job_type is JobType.ECHO
    assert request.payload == {"message": "hello"}
    assert request.priority == DEFAULT_JOB_PRIORITY
    assert request.max_attempts == DEFAULT_MAX_ATTEMPTS
    assert request.idempotency_key == "demo-key-001"


@pytest.mark.parametrize("unsafe_job_type", ["command", "shell", "python", "docker"])
def test_create_job_request_rejects_unsafe_job_types(unsafe_job_type: str) -> None:
    with pytest.raises(ValidationError):
        CreateJobRequest.model_validate(
            {"job_type": unsafe_job_type, "payload": {"command": "echo unsafe"}}
        )


def test_create_job_request_rejects_non_json_payload() -> None:
    with pytest.raises(ValidationError, match="payload must be JSON serializable"):
        CreateJobRequest.model_validate(
            {"job_type": "echo", "payload": {"value": object()}}
        )


def test_job_detail_response_validates_domain_fields() -> None:
    response = _job_detail_response()

    assert response.job_type is JobType.ECHO
    assert response.status is JobStatus.QUEUED
    assert response.attempts == 0
    assert response.max_attempts == 3
    assert response.lease_owner is None
    assert response.lease_expires_at is None


def test_job_detail_response_requires_aware_timestamps() -> None:
    now = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    data = _job_detail_response().model_dump()
    data["created_at"] = datetime(2026, 1, 2, 3, 4, 5)
    data["updated_at"] = now
    data["queued_at"] = now

    with pytest.raises(ValidationError):
        JobDetailResponse.model_validate(data)


def test_create_job_response_marks_idempotent_replays() -> None:
    job = _job_detail_response()
    response = CreateJobResponse(job=job, idempotency_replayed=True)

    assert response.job.id == job.id
    assert response.idempotency_replayed is True


def test_job_list_response_requires_count_to_match_items() -> None:
    job = _job_detail_response()

    response = JobListResponse(items=[job], count=1, limit=50, offset=0)

    assert response.items == [job]
    assert response.count == 1

    with pytest.raises(ValidationError, match="count must equal"):
        JobListResponse(items=[job], count=2, limit=50, offset=0)


def test_cancellation_response_reuses_job_detail_schema() -> None:
    job = _job_detail_response()
    response = CancellationResponse(
        job=job,
        cancellation_requested=True,
        message="cancellation requested",
    )

    assert response.job.status is JobStatus.QUEUED
    assert response.cancellation_requested is True
    assert response.message == "cancellation requested"


def test_terminal_status_helper_matches_documented_terminal_states() -> None:
    assert is_terminal_status(JobStatus.SUCCEEDED) is True
    assert is_terminal_status(JobStatus.FAILED) is True
    assert is_terminal_status(JobStatus.CANCELLED) is True
    assert is_terminal_status(JobStatus.DEAD_LETTERED) is True
    assert is_terminal_status(JobStatus.QUEUED) is False
