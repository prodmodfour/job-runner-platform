from __future__ import annotations

import asyncio
from pathlib import Path
from typing import cast

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from job_runner_platform.api.app import create_app
from job_runner_platform.api.dependencies import get_readiness_service
from job_runner_platform.database.readiness import DatabaseReadinessCheck
from job_runner_platform.queues import InMemoryJobQueue
from job_runner_platform.services import (
    DependencyReadinessResult,
    QueueReadinessCheck,
    ReadinessResult,
    ReadinessService,
)
from job_runner_platform.services.readiness import POSTGRESQL_FAILURE_MESSAGE
from job_runner_platform.settings import Settings


class PassingReadinessCheck:
    async def __call__(self) -> None:
        await asyncio.sleep(0)


class FailingReadinessCheck:
    async def __call__(self) -> None:
        await asyncio.sleep(0)
        raise RuntimeError("secret internal dependency detail")


class FakeReadinessService:
    def __init__(self, result: ReadinessResult) -> None:
        self._result = result

    async def check(self) -> ReadinessResult:
        return self._result


def test_readyz_returns_ready_when_dependency_checks_pass() -> None:
    result = ReadinessResult(
        checks=(
            DependencyReadinessResult(name="postgresql", ready=True),
            DependencyReadinessResult(name="redis", ready=True),
        ),
    )
    client = _client_for_readiness_result(result)

    response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {
            "postgresql": {"status": "ok", "message": None},
            "redis": {"status": "ok", "message": None},
        },
    }


def test_readyz_returns_503_when_a_dependency_check_fails() -> None:
    result = ReadinessResult(
        checks=(
            DependencyReadinessResult(name="postgresql", ready=True),
            DependencyReadinessResult(
                name="redis",
                ready=False,
                message="Redis readiness ping failed",
            ),
        ),
    )
    client = _client_for_readiness_result(result)

    response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {
            "postgresql": {"status": "ok", "message": None},
            "redis": {
                "status": "unavailable",
                "message": "Redis readiness ping failed",
            },
        },
    }


def test_readiness_service_reports_safe_failure_messages() -> None:
    service = ReadinessService(
        database_check=FailingReadinessCheck(),
        queue_check=PassingReadinessCheck(),
    )

    result = asyncio.run(service.check())

    checks = {check.name: check for check in result.checks}
    assert result.is_ready is False
    assert checks["postgresql"].ready is False
    assert checks["postgresql"].message == POSTGRESQL_FAILURE_MESSAGE
    assert "secret" not in str(checks["postgresql"].message)
    assert checks["redis"].ready is True


def test_database_readiness_check_executes_minimal_query(tmp_path: Path) -> None:
    asyncio.run(_exercise_database_readiness_check(tmp_path))


async def _exercise_database_readiness_check(tmp_path: Path) -> None:
    engine, session_factory = _build_sqlite_session_factory(tmp_path)
    try:
        check = DatabaseReadinessCheck(session_factory)
        await check()
    finally:
        await engine.dispose()


def test_queue_readiness_check_uses_queue_abstraction() -> None:
    asyncio.run(_exercise_queue_readiness_check())


async def _exercise_queue_readiness_check() -> None:
    queue = InMemoryJobQueue(ready=True)
    check = QueueReadinessCheck(queue)

    await check()

    queue.set_ready(False)
    service = ReadinessService(
        database_check=PassingReadinessCheck(),
        queue_check=check,
    )
    result = await service.check()

    checks = {check_result.name: check_result for check_result in result.checks}
    assert result.is_ready is False
    assert checks["redis"].ready is False
    assert checks["redis"].message == "Redis readiness ping failed"


def _client_for_readiness_result(result: ReadinessResult) -> TestClient:
    app = create_app(
        Settings(
            app_name="test-job-runner",
            app_version="test-version",
            environment="test",
        ),
    )
    fake = FakeReadinessService(result)

    def override_readiness_service() -> ReadinessService:
        return cast(ReadinessService, fake)

    app.dependency_overrides[get_readiness_service] = override_readiness_service
    return TestClient(app)


def _build_sqlite_session_factory(
    tmp_path: Path,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'ready.db'}")
    session_factory = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        autoflush=False,
    )
    return engine, session_factory
