from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from job_runner_platform.api.app import create_app
from job_runner_platform.api.dependencies import get_job_service
from job_runner_platform.database.models import JobModel
from job_runner_platform.domain.jobs import (
    DEFAULT_JOB_PRIORITY,
    DEFAULT_MAX_ATTEMPTS,
    IdempotencyKey,
    JobPayload,
    JobPriority,
    JobStatus,
    JobType,
    MaxAttempts,
)
from job_runner_platform.services import (
    DEFAULT_LIST_LIMIT,
    JobCancellationConflictError,
    JobCancellationResult,
    JobCreationResult,
    JobListResult,
    JobNotFoundError,
    JobService,
)
from job_runner_platform.settings import Settings


@dataclass(frozen=True, slots=True)
class CreateCall:
    job_type: JobType | str
    payload: JobPayload | None
    priority: JobPriority
    max_attempts: MaxAttempts
    idempotency_key: IdempotencyKey | None


@dataclass(frozen=True, slots=True)
class ListCall:
    limit: int
    offset: int
    status: JobStatus | str | None


class FakeJobService:
    def __init__(self) -> None:
        self.created_job = _job_model(job_type=JobType.ECHO)
        self.create_replayed = False
        self.create_calls: list[CreateCall] = []
        self.list_calls: list[ListCall] = []
        self.jobs: dict[UUID, JobModel] = {}
        self.list_items: tuple[JobModel, ...] = ()
        self.conflicting_cancel_ids: set[UUID] = set()

    async def create_job(
        self,
        *,
        job_type: JobType | str,
        payload: JobPayload | None = None,
        priority: JobPriority = DEFAULT_JOB_PRIORITY,
        max_attempts: MaxAttempts = DEFAULT_MAX_ATTEMPTS,
        idempotency_key: IdempotencyKey | None = None,
    ) -> JobCreationResult:
        self.create_calls.append(
            CreateCall(
                job_type=job_type,
                payload=payload,
                priority=priority,
                max_attempts=max_attempts,
                idempotency_key=idempotency_key,
            )
        )
        self.jobs.setdefault(self.created_job.id, self.created_job)
        return JobCreationResult(
            job=self.created_job,
            idempotency_replayed=self.create_replayed,
        )

    async def get_job(self, job_id: UUID) -> JobModel | None:
        return self.jobs.get(job_id)

    async def list_jobs(
        self,
        *,
        limit: int = DEFAULT_LIST_LIMIT,
        offset: int = 0,
        status: JobStatus | str | None = None,
    ) -> JobListResult:
        self.list_calls.append(ListCall(limit=limit, offset=offset, status=status))
        items = self.list_items or tuple(self.jobs.values())
        return JobListResult(
            items=items,
            count=len(items),
            limit=limit,
            offset=offset,
        )

    async def cancel_job(self, job_id: UUID) -> JobCancellationResult:
        if job_id in self.conflicting_cancel_ids:
            raise JobCancellationConflictError(
                f"job {job_id} is already terminal with status succeeded"
            )

        job = self.jobs.get(job_id)
        if job is None:
            raise JobNotFoundError(f"job {job_id} was not found")

        cancelled = _job_model(
            job_id=job_id,
            job_type=JobType(job.job_type),
            status=JobStatus.CANCELLED,
            payload=job.payload,
            idempotency_key=job.idempotency_key,
        )
        return JobCancellationResult(
            job=cancelled,
            cancellation_requested=True,
            message="queued job cancelled",
        )


def test_create_job_route_returns_created_job_response() -> None:
    fake = FakeJobService()
    fake.created_job = _job_model(
        job_type=JobType.ECHO,
        payload={"message": "hello"},
        priority=5,
        max_attempts=4,
        idempotency_key="demo-key-001",
    )
    client = _client_for(fake)

    response = client.post(
        "/jobs",
        json={
            "job_type": "echo",
            "payload": {"message": "hello"},
            "priority": 5,
            "max_attempts": 4,
            "idempotency_key": "demo-key-001",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["idempotency_replayed"] is False
    assert body["job"]["id"] == str(fake.created_job.id)
    assert body["job"]["job_type"] == "echo"
    assert body["job"]["status"] == "queued"
    assert body["job"]["payload"] == {"message": "hello"}
    assert fake.create_calls == [
        CreateCall(
            job_type=JobType.ECHO,
            payload={"message": "hello"},
            priority=5,
            max_attempts=4,
            idempotency_key="demo-key-001",
        )
    ]


def test_create_job_route_returns_ok_for_idempotency_replay() -> None:
    fake = FakeJobService()
    fake.create_replayed = True
    fake.created_job = _job_model(
        job_type=JobType.CHECKSUM,
        payload={"text": "hello"},
        idempotency_key="demo-key-replay",
    )
    client = _client_for(fake)

    response = client.post(
        "/jobs",
        json={
            "job_type": "checksum",
            "payload": {"text": "hello"},
            "idempotency_key": "demo-key-replay",
        },
    )

    assert response.status_code == 200
    assert response.json()["idempotency_replayed"] is True


def test_list_jobs_route_supports_pagination_and_status_filter() -> None:
    fake = FakeJobService()
    first = _job_model(job_type=JobType.ECHO, status=JobStatus.QUEUED)
    second = _job_model(job_type=JobType.SLEEP, status=JobStatus.QUEUED)
    fake.list_items = (first, second)
    client = _client_for(fake)

    response = client.get("/jobs", params={"limit": 2, "offset": 5, "status": "queued"})

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert body["limit"] == 2
    assert body["offset"] == 5
    assert [item["id"] for item in body["items"]] == [str(first.id), str(second.id)]
    assert fake.list_calls == [ListCall(limit=2, offset=5, status=JobStatus.QUEUED)]


def test_get_job_route_returns_job_or_404() -> None:
    fake = FakeJobService()
    job = _job_model(job_type=JobType.ECHO, payload={"message": "hello"})
    fake.jobs[job.id] = job
    client = _client_for(fake)

    response = client.get(f"/jobs/{job.id}")
    missing_response = client.get(f"/jobs/{uuid4()}")

    assert response.status_code == 200
    assert response.json()["id"] == str(job.id)
    assert response.json()["payload"] == {"message": "hello"}
    assert missing_response.status_code == 404
    assert "was not found" in missing_response.json()["detail"]


def test_cancel_job_route_returns_cancellation_response_or_errors() -> None:
    fake = FakeJobService()
    queued_job = _job_model(job_type=JobType.SLEEP, status=JobStatus.QUEUED)
    terminal_job = _job_model(job_type=JobType.ECHO, status=JobStatus.SUCCEEDED)
    fake.jobs[queued_job.id] = queued_job
    fake.jobs[terminal_job.id] = terminal_job
    fake.conflicting_cancel_ids.add(terminal_job.id)
    client = _client_for(fake)

    cancelled_response = client.post(f"/jobs/{queued_job.id}/cancel")
    missing_response = client.post(f"/jobs/{uuid4()}/cancel")
    conflict_response = client.post(f"/jobs/{terminal_job.id}/cancel")

    assert cancelled_response.status_code == 200
    cancelled_body = cancelled_response.json()
    assert cancelled_body["cancellation_requested"] is True
    assert cancelled_body["message"] == "queued job cancelled"
    assert cancelled_body["job"]["status"] == "cancelled"
    assert missing_response.status_code == 404
    assert conflict_response.status_code == 409
    assert "already terminal" in conflict_response.json()["detail"]


def test_job_routes_validate_request_inputs_before_calling_service() -> None:
    fake = FakeJobService()
    client = _client_for(fake)

    invalid_type_response = client.post(
        "/jobs",
        json={"job_type": "command", "payload": {"command": "not allowed"}},
    )
    invalid_limit_response = client.get("/jobs", params={"limit": 101})
    invalid_status_response = client.get("/jobs", params={"status": "not-a-status"})

    assert invalid_type_response.status_code == 422
    assert invalid_limit_response.status_code == 422
    assert invalid_status_response.status_code == 422
    assert fake.create_calls == []
    assert fake.list_calls == []


def _client_for(fake: FakeJobService) -> TestClient:
    app = create_app(
        Settings(
            app_name="test-job-runner",
            app_version="test-version",
            environment="test",
        )
    )

    def override_job_service() -> JobService:
        return cast(JobService, fake)

    app.dependency_overrides[get_job_service] = override_job_service
    return TestClient(app)


def _job_model(
    *,
    job_id: UUID | None = None,
    job_type: JobType,
    status: JobStatus = JobStatus.QUEUED,
    payload: JobPayload | None = None,
    priority: JobPriority = DEFAULT_JOB_PRIORITY,
    attempts: int = 0,
    max_attempts: MaxAttempts = DEFAULT_MAX_ATTEMPTS,
    idempotency_key: IdempotencyKey | None = None,
) -> JobModel:
    now = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    return JobModel(
        id=job_id or uuid4(),
        job_type=job_type.value,
        status=status.value,
        priority=priority,
        payload=dict(payload or {}),
        result=None,
        error_message=None,
        attempts=attempts,
        max_attempts=max_attempts,
        idempotency_key=idempotency_key,
        lease_owner=None,
        lease_expires_at=None,
        created_at=now,
        updated_at=now,
        queued_at=now,
        started_at=None,
        finished_at=now if status is JobStatus.CANCELLED else None,
    )
