from __future__ import annotations

import json
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from job_runner_platform.domain.jobs import (
    DEFAULT_JOB_PRIORITY,
    DEFAULT_MAX_ATTEMPTS,
    ErrorMessage,
    IdempotencyKey,
    JobAttempts,
    JobId,
    JobPayload,
    JobPriority,
    JobResult,
    JobStatus,
    JobTimestamp,
    JobType,
    LeaseExpiry,
    LeaseOwner,
    MaxAttempts,
)


class ApiSchema(BaseModel):
    """Base configuration for public API request and response schemas."""

    model_config = ConfigDict(extra="forbid", frozen=True, from_attributes=True)


class HealthResponse(ApiSchema):
    """Response body for the liveness endpoint."""

    status: Literal["ok"]
    app_name: str
    app_version: str
    environment: str


class ReadinessCheckResponse(ApiSchema):
    """Readiness state for one external dependency."""

    status: Literal["ok", "unavailable"]
    message: str | None = None


class ReadinessResponse(ApiSchema):
    """Response body for dependency readiness checks."""

    status: Literal["ready", "not_ready"]
    checks: dict[str, ReadinessCheckResponse]


class CreateJobRequest(ApiSchema):
    """Request body for submitting a safe allowlisted demo job."""

    job_type: JobType
    payload: JobPayload = Field(default_factory=dict)
    priority: JobPriority = DEFAULT_JOB_PRIORITY
    max_attempts: MaxAttempts = DEFAULT_MAX_ATTEMPTS
    idempotency_key: IdempotencyKey | None = None

    @field_validator("payload")
    @classmethod
    def payload_must_be_json_serializable(cls, value: JobPayload) -> JobPayload:
        """Reject payload values that cannot be safely stored as JSON."""

        _validate_json_object(value, "payload")
        return value


class JobDetailResponse(ApiSchema):
    """Full public representation of a job."""

    id: JobId
    job_type: JobType
    status: JobStatus
    priority: JobPriority
    attempts: JobAttempts
    max_attempts: MaxAttempts
    payload: JobPayload
    result: JobResult | None = None
    error_message: ErrorMessage | None = None
    idempotency_key: IdempotencyKey | None = None
    created_at: JobTimestamp
    updated_at: JobTimestamp
    queued_at: JobTimestamp
    started_at: JobTimestamp | None = None
    finished_at: JobTimestamp | None = None
    lease_owner: LeaseOwner | None = None
    lease_expires_at: LeaseExpiry | None = None

    @field_validator("payload", "result")
    @classmethod
    def json_fields_must_be_serializable(
        cls,
        value: JobPayload | JobResult | None,
    ) -> JobPayload | JobResult | None:
        """Reject response JSON objects that cannot be serialized."""

        if value is not None:
            _validate_json_object(value, "job JSON field")
        return value


class CreateJobResponse(ApiSchema):
    """Response body returned after creating or replaying a job submission."""

    job: JobDetailResponse
    idempotency_replayed: bool = False


class JobListResponse(ApiSchema):
    """Paginated job listing response."""

    items: list[JobDetailResponse]
    count: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)

    @model_validator(mode="after")
    def count_must_match_items(self) -> Self:
        """Keep the explicit count aligned with the returned page contents."""

        if self.count != len(self.items):
            message = "count must equal the number of returned items"
            raise ValueError(message)
        return self


class CancellationResponse(ApiSchema):
    """Response body for a job cancellation request."""

    job: JobDetailResponse
    cancellation_requested: bool
    message: str


def _validate_json_object(value: JobPayload | JobResult, field_name: str) -> None:
    try:
        json.dumps(value)
    except (TypeError, ValueError) as exc:
        message = f"{field_name} must be JSON serializable"
        raise ValueError(message) from exc
