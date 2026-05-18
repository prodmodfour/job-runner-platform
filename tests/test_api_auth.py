from __future__ import annotations

from typing import cast

from fastapi.testclient import TestClient

from job_runner_platform.api.app import create_app
from job_runner_platform.api.auth import API_KEY_HEADER_NAME
from job_runner_platform.api.dependencies import get_job_service, get_readiness_service
from job_runner_platform.domain.jobs import JobStatus
from job_runner_platform.services import (
    DEFAULT_LIST_LIMIT,
    DependencyReadinessResult,
    JobListResult,
    JobService,
    ReadinessResult,
    ReadinessService,
)
from job_runner_platform.settings import Settings


class FakeJobService:
    def __init__(self) -> None:
        self.list_calls: list[tuple[int, int, JobStatus | str | None]] = []

    async def list_jobs(
        self,
        *,
        limit: int = DEFAULT_LIST_LIMIT,
        offset: int = 0,
        status: JobStatus | str | None = None,
    ) -> JobListResult:
        self.list_calls.append((limit, offset, status))
        return JobListResult(items=(), count=0, limit=limit, offset=offset)


class FakeReadinessService:
    async def check(self) -> ReadinessResult:
        return ReadinessResult(
            checks=(
                DependencyReadinessResult(name="postgresql", ready=True),
                DependencyReadinessResult(name="redis", ready=True),
            ),
        )


def test_business_routes_allow_requests_when_auth_is_disabled() -> None:
    fake = FakeJobService()
    client = _client_for_job_service(fake, _settings(auth_enabled=False))

    response = client.get("/jobs")

    assert response.status_code == 200
    assert response.json() == {"items": [], "count": 0, "limit": 50, "offset": 0}
    assert fake.list_calls == [(50, 0, None)]


def test_business_routes_reject_missing_api_key_when_auth_is_enabled() -> None:
    fake = FakeJobService()
    client = _client_for_job_service(fake, _settings(auth_enabled=True))

    response = client.get("/jobs")

    assert response.status_code == 401
    assert response.json()["detail"] == "API key is required"
    assert fake.list_calls == []


def test_business_routes_reject_invalid_api_key_when_auth_is_enabled() -> None:
    fake = FakeJobService()
    client = _client_for_job_service(fake, _settings(auth_enabled=True))

    response = client.get("/jobs", headers={API_KEY_HEADER_NAME: "wrong-demo-key"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API key"
    assert fake.list_calls == []


def test_business_routes_accept_valid_api_key_when_auth_is_enabled() -> None:
    fake = FakeJobService()
    client = _client_for_job_service(fake, _settings(auth_enabled=True))

    response = client.get("/jobs", headers={API_KEY_HEADER_NAME: "valid-demo-key"})

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert fake.list_calls == [(50, 0, None)]


def test_system_endpoints_are_not_protected_when_auth_is_enabled() -> None:
    app = create_app(_settings(auth_enabled=True))
    fake_readiness = FakeReadinessService()

    def override_readiness_service() -> ReadinessService:
        return cast(ReadinessService, fake_readiness)

    app.dependency_overrides[get_readiness_service] = override_readiness_service
    client = TestClient(app)

    assert client.get("/healthz").status_code == 200
    assert client.get("/readyz").status_code == 200
    assert client.get("/metrics").status_code == 200


def _client_for_job_service(fake: FakeJobService, settings: Settings) -> TestClient:
    app = create_app(settings)

    def override_job_service() -> JobService:
        return cast(JobService, fake)

    app.dependency_overrides[get_job_service] = override_job_service
    return TestClient(app)


def _settings(*, auth_enabled: bool) -> Settings:
    return Settings(
        app_name="test-job-runner",
        app_version="test-version",
        environment="test",
        auth_enabled=auth_enabled,
        auth_api_keys=("valid-demo-key", "backup-demo-key"),
    )
