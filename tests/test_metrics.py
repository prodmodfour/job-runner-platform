from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from job_runner_platform.api.app import create_app
from job_runner_platform.database.base import Base
from job_runner_platform.database.session import session_scope
from job_runner_platform.domain.jobs import JobStatus, JobType
from job_runner_platform.queues import InMemoryJobQueue
from job_runner_platform.repositories import JobRepository
from job_runner_platform.services import JobService
from job_runner_platform.services.worker import JobWorkerService, WorkerProcessOutcome
from job_runner_platform.settings import Settings


@dataclass(slots=True)
class RecordingMetrics:
    jobs_created: int = 0
    jobs_started: int = 0
    jobs_succeeded: int = 0
    jobs_failed: int = 0
    jobs_retried: int = 0
    jobs_dead_lettered: int = 0
    jobs_cancelled: int = 0
    job_durations: list[float] = field(default_factory=list)
    api_requests: list[tuple[str, str, int, float]] = field(default_factory=list)
    worker_outcomes: list[str] = field(default_factory=list)
    queue_polls: list[bool] = field(default_factory=list)

    def record_job_created(self) -> None:
        self.jobs_created += 1

    def record_job_started(self) -> None:
        self.jobs_started += 1

    def record_job_succeeded(self) -> None:
        self.jobs_succeeded += 1

    def record_job_failed(self) -> None:
        self.jobs_failed += 1

    def record_job_retried(self) -> None:
        self.jobs_retried += 1

    def record_job_dead_lettered(self) -> None:
        self.jobs_dead_lettered += 1

    def record_job_cancelled(self) -> None:
        self.jobs_cancelled += 1

    def record_job_duration(self, duration_seconds: float) -> None:
        self.job_durations.append(duration_seconds)

    def record_api_request(
        self,
        *,
        method: str,
        path: str,
        status_code: int,
        duration_seconds: float,
    ) -> None:
        self.api_requests.append((method, path, status_code, duration_seconds))

    def record_worker_poll(self, *, outcome: str) -> None:
        self.worker_outcomes.append(outcome)

    def record_queue_poll(self, *, message_received: bool) -> None:
        self.queue_polls.append(message_received)


def test_metrics_endpoint_exposes_prometheus_payload_and_key_metric_names() -> None:
    app = create_app(
        Settings(
            app_name="test-job-runner",
            app_version="test-version",
            environment="test",
        ),
    )
    client = TestClient(app)

    assert client.get("/healthz").status_code == 200
    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    text = response.text
    for metric_name in (
        "jobs_created_total",
        "jobs_started_total",
        "jobs_succeeded_total",
        "jobs_failed_total",
        "jobs_retried_total",
        "jobs_dead_lettered_total",
        "jobs_cancelled_total",
        "job_duration_seconds",
    ):
        assert metric_name in text
    assert "api_requests_total" in text
    assert 'path="/healthz"' in text


def test_job_service_records_created_and_queued_cancellation_metrics(
    tmp_path: Path,
) -> None:
    asyncio.run(_exercise_job_service_metrics(tmp_path))


async def _exercise_job_service_metrics(tmp_path: Path) -> None:
    engine, session_factory = await _build_sqlite_session_factory(tmp_path)
    try:
        queue = InMemoryJobQueue()
        metrics = RecordingMetrics()
        async with session_scope(session_factory) as session:
            repository = JobRepository(session)
            service = JobService(
                repository=repository,
                queue=queue,
                metrics=metrics,
            )

            created = await service.create_job(job_type=JobType.SLEEP)
            cancellation = await service.cancel_job(created.job.id)

            assert cancellation.job.status == JobStatus.CANCELLED.value
            assert metrics.jobs_created == 1
            assert metrics.jobs_cancelled == 1
    finally:
        await engine.dispose()


def test_worker_service_records_success_polling_and_duration_metrics(
    tmp_path: Path,
) -> None:
    asyncio.run(_exercise_worker_success_metrics(tmp_path))


async def _exercise_worker_success_metrics(tmp_path: Path) -> None:
    engine, session_factory = await _build_sqlite_session_factory(tmp_path)
    try:
        queue = InMemoryJobQueue()
        metrics = RecordingMetrics()
        async with session_scope(session_factory) as session:
            repository = JobRepository(session)
            job = await repository.create_job(
                job_type=JobType.ECHO,
                payload={"message": "metrics"},
            )
            await queue.enqueue(job.id)

        service = JobWorkerService(
            session_factory=session_factory,
            queue=queue,
            worker_id="metrics-worker-success",
            lease_seconds=60.0,
            metrics=metrics,
        )

        result = await service.process_one_job(timeout_seconds=0)

        assert result.outcome is WorkerProcessOutcome.SUCCEEDED
        assert metrics.jobs_started == 1
        assert metrics.jobs_succeeded == 1
        assert metrics.queue_polls == [True]
        assert metrics.worker_outcomes == [WorkerProcessOutcome.SUCCEEDED.value]
        assert len(metrics.job_durations) == 1
        assert metrics.job_durations[0] >= 0.0
    finally:
        await engine.dispose()


def test_worker_service_records_retry_and_dead_letter_metrics(tmp_path: Path) -> None:
    asyncio.run(_exercise_worker_failure_metrics(tmp_path))


async def _exercise_worker_failure_metrics(tmp_path: Path) -> None:
    engine, session_factory = await _build_sqlite_session_factory(tmp_path)
    try:
        queue = InMemoryJobQueue()
        metrics = RecordingMetrics()
        async with session_scope(session_factory) as session:
            repository = JobRepository(session)
            job = await repository.create_job(
                job_type=JobType.ALWAYS_FAIL,
                max_attempts=2,
            )
            await queue.enqueue(job.id)

        service = JobWorkerService(
            session_factory=session_factory,
            queue=queue,
            worker_id="metrics-worker-failure",
            lease_seconds=60.0,
            metrics=metrics,
        )

        retry_result = await service.process_one_job(timeout_seconds=0)
        dead_letter_result = await service.process_one_job(timeout_seconds=0)

        assert retry_result.outcome is WorkerProcessOutcome.RETRIED
        assert dead_letter_result.outcome is WorkerProcessOutcome.DEAD_LETTERED
        assert metrics.jobs_started == 2
        assert metrics.jobs_failed == 2
        assert metrics.jobs_retried == 1
        assert metrics.jobs_dead_lettered == 1
        assert metrics.queue_polls == [True, True]
        assert metrics.worker_outcomes == [
            WorkerProcessOutcome.RETRIED.value,
            WorkerProcessOutcome.DEAD_LETTERED.value,
        ]
        assert len(metrics.job_durations) == 2
    finally:
        await engine.dispose()


async def _build_sqlite_session_factory(
    tmp_path: Path,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'metrics.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        autoflush=False,
    )
    return engine, session_factory
