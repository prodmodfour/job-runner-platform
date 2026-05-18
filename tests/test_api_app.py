from __future__ import annotations

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from job_runner_platform.api.app import create_app
from job_runner_platform.logging import REQUEST_ID_HEADER
from job_runner_platform.settings import Settings


def make_settings(
    *,
    app_name: str = "test-job-runner",
    app_version: str = "test-version",
    environment: str = "test",
    log_level: str = "INFO",
    docs_enabled: bool = False,
) -> Settings:
    return Settings(
        app_name=app_name,
        app_version=app_version,
        environment=environment,
        log_level=log_level,
        docs_enabled=docs_enabled,
    )


def test_health_endpoint_returns_application_metadata() -> None:
    app = create_app(make_settings())
    client = TestClient(app)

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "app_name": "test-job-runner",
        "app_version": "test-version",
        "environment": "test",
    }


def test_request_id_header_is_propagated() -> None:
    client = TestClient(create_app(make_settings()))
    request_id = "test-request-id-001"

    response = client.get("/healthz", headers={REQUEST_ID_HEADER: request_id})

    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == request_id


def test_request_id_header_is_generated_when_absent() -> None:
    client = TestClient(create_app(make_settings()))

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER]


def test_docs_are_disabled_by_default(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("JOB_RUNNER_DOCS_ENABLED", raising=False)
    settings = Settings(
        app_name="test-job-runner",
        app_version="test-version",
        environment="test",
        log_level="INFO",
    )
    client = TestClient(create_app(settings))

    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_docs_can_be_enabled_by_configuration() -> None:
    client = TestClient(create_app(make_settings(docs_enabled=True)))

    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_settings_load_from_job_runner_environment(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("JOB_RUNNER_APP_NAME", "env-job-runner")
    monkeypatch.setenv("JOB_RUNNER_APP_VERSION", "env-version")
    monkeypatch.setenv("JOB_RUNNER_ENVIRONMENT", "env-test")
    monkeypatch.setenv("JOB_RUNNER_LOG_LEVEL", "debug")
    monkeypatch.setenv("JOB_RUNNER_DOCS_ENABLED", "true")
    monkeypatch.setenv("JOB_RUNNER_REDIS_URL", "redis://localhost:6379/5")

    settings = Settings()

    assert settings.app_name == "env-job-runner"
    assert settings.app_version == "env-version"
    assert settings.environment == "env-test"
    assert settings.log_level == "DEBUG"
    assert settings.docs_enabled is True
    assert settings.redis_url == "redis://localhost:6379/5"
