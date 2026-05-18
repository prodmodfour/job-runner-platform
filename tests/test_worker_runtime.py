from __future__ import annotations

import asyncio
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from job_runner_platform.database.base import Base
from job_runner_platform.database.session import session_scope
from job_runner_platform.domain.jobs import JobStatus, JobType
from job_runner_platform.queues import InMemoryJobQueue
from job_runner_platform.repositories import JobRepository
from job_runner_platform.services.worker import JobWorkerService, WorkerProcessOutcome
from job_runner_platform.worker import WorkerRuntime, WorkerRuntimeConfig


def test_worker_runtime_claims_runs_and_completes_echo_job(tmp_path: Path) -> None:
    asyncio.run(_exercise_worker_success_path(tmp_path))


async def _exercise_worker_success_path(tmp_path: Path) -> None:
    engine, session_factory = await _build_sqlite_session_factory(tmp_path)
    try:
        queue = InMemoryJobQueue()
        async with session_scope(session_factory) as session:
            repository = JobRepository(session)
            job = await repository.create_job(
                job_type=JobType.ECHO,
                payload={"message": "hello"},
            )
            job_id = job.id
            await queue.enqueue(job_id)

        runtime = _build_runtime(
            session_factory=session_factory,
            queue=queue,
            worker_id="worker-success",
        )

        result = await runtime.run_once()

        assert result.outcome is WorkerProcessOutcome.SUCCEEDED
        assert result.job_id == job_id
        assert result.job_status is JobStatus.SUCCEEDED
        assert queue.pending_count == 0

        async with session_factory() as session:
            stored = await JobRepository(session).get_job_by_id(job_id)
            assert stored is not None
            assert stored.status == JobStatus.SUCCEEDED.value
            assert stored.result == {"payload": {"message": "hello"}}
            assert stored.error_message is None
            assert stored.attempts == 1
            assert stored.lease_owner is None
            assert stored.lease_expires_at is None
            assert stored.started_at is not None
            assert stored.finished_at is not None
    finally:
        await engine.dispose()


def test_worker_runtime_safely_skips_duplicate_dispatch_signal(
    tmp_path: Path,
) -> None:
    asyncio.run(_exercise_worker_duplicate_signal_safety(tmp_path))


async def _exercise_worker_duplicate_signal_safety(tmp_path: Path) -> None:
    engine, session_factory = await _build_sqlite_session_factory(tmp_path)
    try:
        queue = InMemoryJobQueue()
        async with session_scope(session_factory) as session:
            repository = JobRepository(session)
            job = await repository.create_job(job_type=JobType.ECHO)
            job_id = job.id
            await queue.enqueue(job_id)
            await queue.enqueue(job_id)

        runtime = _build_runtime(
            session_factory=session_factory,
            queue=queue,
            worker_id="worker-duplicates",
        )

        first_result = await runtime.run_once()
        second_result = await runtime.run_once()

        assert first_result.outcome is WorkerProcessOutcome.SUCCEEDED
        assert second_result.outcome is WorkerProcessOutcome.CLAIM_SKIPPED
        assert second_result.job_id == job_id
        assert queue.pending_count == 0

        async with session_factory() as session:
            stored = await JobRepository(session).get_job_by_id(job_id)
            assert stored is not None
            assert stored.status == JobStatus.SUCCEEDED.value
            assert stored.attempts == 1
    finally:
        await engine.dispose()


def test_worker_runtime_records_handler_failure(tmp_path: Path) -> None:
    asyncio.run(_exercise_worker_failure_path(tmp_path))


async def _exercise_worker_failure_path(tmp_path: Path) -> None:
    engine, session_factory = await _build_sqlite_session_factory(tmp_path)
    try:
        queue = InMemoryJobQueue()
        async with session_scope(session_factory) as session:
            repository = JobRepository(session)
            job = await repository.create_job(job_type=JobType.ALWAYS_FAIL)
            job_id = job.id
            await queue.enqueue(job_id)

        runtime = _build_runtime(
            session_factory=session_factory,
            queue=queue,
            worker_id="worker-failure",
        )

        result = await runtime.run_once()

        assert result.outcome is WorkerProcessOutcome.FAILED
        assert result.job_id == job_id
        assert result.job_status is JobStatus.FAILED
        assert result.error_message is not None
        assert "always_fail intentionally failed" in result.error_message

        async with session_factory() as session:
            stored = await JobRepository(session).get_job_by_id(job_id)
            assert stored is not None
            assert stored.status == JobStatus.FAILED.value
            assert stored.result is None
            assert stored.error_message is not None
            assert "always_fail intentionally failed" in stored.error_message
            assert stored.attempts == 1
            assert stored.lease_owner is None
            assert stored.lease_expires_at is None
            assert stored.finished_at is not None
    finally:
        await engine.dispose()


def _build_runtime(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    queue: InMemoryJobQueue,
    worker_id: str,
) -> WorkerRuntime:
    config = WorkerRuntimeConfig(
        worker_id=worker_id,
        poll_seconds=0.01,
        lease_seconds=60.0,
    )
    service = JobWorkerService(
        session_factory=session_factory,
        queue=queue,
        worker_id=config.worker_id,
        lease_seconds=config.lease_seconds,
    )
    return WorkerRuntime(service=service, config=config)


async def _build_sqlite_session_factory(
    tmp_path: Path,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'worker.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        autoflush=False,
    )
    return engine, session_factory
