from __future__ import annotations

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]


def test_dockerfile_uses_non_root_runtime_user_and_healthcheck() -> None:
    dockerfile = (ROOT_DIR / "Dockerfile").read_text(encoding="utf-8")

    assert "FROM python:3.12-slim AS runtime" in dockerfile
    assert "useradd --system" in dockerfile
    assert "USER app" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "http://127.0.0.1:8000/healthz" in dockerfile
    assert "job_runner_platform.api.app:app" in dockerfile


def test_docker_compose_defines_required_local_services() -> None:
    compose = (ROOT_DIR / "docker-compose.yml").read_text(encoding="utf-8")

    for service_name in (
        "api",
        "worker",
        "postgres",
        "redis",
        "prometheus",
        "grafana",
    ):
        assert f"  {service_name}:" in compose

    assert (
        "postgresql+asyncpg://job_runner:job_runner@postgres:5432/job_runner" in compose
    )
    assert "redis://redis:6379/0" in compose
    assert "127.0.0.1:8000:8000" in compose
    assert 'JOB_RUNNER_AUTH_ENABLED: "false"' in compose


def test_docker_compose_declares_health_checks_and_dependency_order() -> None:
    compose = (ROOT_DIR / "docker-compose.yml").read_text(encoding="utf-8")

    assert "pg_isready -U job_runner -d job_runner" in compose
    assert "redis-cli" in compose
    assert "http://127.0.0.1:8000/healthz" in compose
    assert "condition: service_healthy" in compose
    assert "JOB_RUNNER_WORKER_ID: compose-worker-1" in compose
