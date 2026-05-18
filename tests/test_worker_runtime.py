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
from job_runner_platform.domain.jobs import JobPayload, JobResult, JobStatus, JobType
from job_runner_platform.handlers import JobHandlerContext
from job_runner_platform.queues import InMemoryJobQueue
from job_runner_platform.repositories import JobRepository
from job_runner_platform.services.worker import (
    MAX_RECORDED_ERROR_MESSAGE_LENGTH,
    JobWorkerService,
    WorkerProcessOutcome,
)
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


def test_worker_runtime_retries_fail_once_job_then_succeeds(tmp_path: Path) -> None:
    asyncio.run(_exercise_worker_fail_once_retry_success(tmp_path))


async def _exercise_worker_fail_once_retry_success(tmp_path: Path) -> None:
    engine, session_factory = await _build_sqlite_session_factory(tmp_path)
    try:
        queue = InMemoryJobQueue()
        async with session_scope(session_factory) as session:
            repository = JobRepository(session)
            job = await repository.create_job(job_type=JobType.FAIL_ONCE)
            job_id = job.id
            await queue.enqueue(job_id)

        runtime = _build_runtime(
            session_factory=session_factory,
            queue=queue,
            worker_id="worker-fail-once",
        )

        first_result = await runtime.run_once()

        assert first_result.outcome is WorkerProcessOutcome.RETRIED
        assert first_result.job_id == job_id
        assert first_result.job_status is JobStatus.QUEUED
        assert first_result.error_message is not None
        assert "fail_once intentionally failed" in first_result.error_message
        assert queue.pending_count == 1

        async with session_factory() as session:
            stored_after_retry = await JobRepository(session).get_job_by_id(job_id)
            assert stored_after_retry is not None
            assert stored_after_retry.status == JobStatus.QUEUED.value
            assert stored_after_retry.result is None
            assert stored_after_retry.error_message is not None
            assert "fail_once intentionally failed" in stored_after_retry.error_message
            assert stored_after_retry.attempts == 1
            assert stored_after_retry.lease_owner is None
            assert stored_after_retry.lease_expires_at is None
            assert stored_after_retry.started_at is None
            assert stored_after_retry.finished_at is None

        second_result = await runtime.run_once()

        assert second_result.outcome is WorkerProcessOutcome.SUCCEEDED
        assert second_result.job_id == job_id
        assert second_result.job_status is JobStatus.SUCCEEDED
        assert queue.pending_count == 0

        async with session_factory() as session:
            stored_after_success = await JobRepository(session).get_job_by_id(job_id)
            assert stored_after_success is not None
            assert stored_after_success.status == JobStatus.SUCCEEDED.value
            assert stored_after_success.result == {"failed_once": True, "attempt": 2}
            assert stored_after_success.error_message is None
            assert stored_after_success.attempts == 2
            assert stored_after_success.lease_owner is None
            assert stored_after_success.lease_expires_at is None
            assert stored_after_success.started_at is not None
            assert stored_after_success.finished_at is not None
    finally:
        await engine.dispose()


def test_worker_runtime_dead_letters_always_fail_after_max_attempts(
    tmp_path: Path,
) -> None:
    asyncio.run(_exercise_worker_always_fail_dead_letter(tmp_path))


async def _exercise_worker_always_fail_dead_letter(tmp_path: Path) -> None:
    engine, session_factory = await _build_sqlite_session_factory(tmp_path)
    try:
        queue = InMemoryJobQueue()
        async with session_scope(session_factory) as session:
            repository = JobRepository(session)
            job = await repository.create_job(
                job_type=JobType.ALWAYS_FAIL,
                max_attempts=2,
            )
            job_id = job.id
            await queue.enqueue(job_id)

        runtime = _build_runtime(
            session_factory=session_factory,
            queue=queue,
            worker_id="worker-dead-letter",
        )

        retry_result = await runtime.run_once()
        dead_letter_result = await runtime.run_once()

        assert retry_result.outcome is WorkerProcessOutcome.RETRIED
        assert retry_result.job_status is JobStatus.QUEUED
        assert dead_letter_result.outcome is WorkerProcessOutcome.DEAD_LETTERED
        assert dead_letter_result.job_id == job_id
        assert dead_letter_result.job_status is JobStatus.DEAD_LETTERED
        assert dead_letter_result.error_message is not None
        assert "always_fail intentionally failed" in dead_letter_result.error_message
        assert queue.pending_count == 0

        async with session_factory() as session:
            stored = await JobRepository(session).get_job_by_id(job_id)
            assert stored is not None
            assert stored.status == JobStatus.DEAD_LETTERED.value
            assert stored.result is None
            assert stored.error_message is not None
            assert "always_fail intentionally failed" in stored.error_message
            assert stored.attempts == 2
            assert stored.max_attempts == 2
            assert stored.lease_owner is None
            assert stored.lease_expires_at is None
            assert stored.finished_at is not None
    finally:
        await engine.dispose()


def test_worker_runtime_honours_single_max_attempt_and_records_error(
    tmp_path: Path,
) -> None:
    asyncio.run(_exercise_worker_single_max_attempt(tmp_path))


async def _exercise_worker_single_max_attempt(tmp_path: Path) -> None:
    engine, session_factory = await _build_sqlite_session_factory(tmp_path)
    try:
        queue = InMemoryJobQueue()
        async with session_scope(session_factory) as session:
            repository = JobRepository(session)
            job = await repository.create_job(
                job_type=JobType.ALWAYS_FAIL,
                max_attempts=1,
            )
            job_id = job.id
            await queue.enqueue(job_id)

        runtime = _build_runtime(
            session_factory=session_factory,
            queue=queue,
            worker_id="worker-one-attempt",
        )

        result = await runtime.run_once()

        assert result.outcome is WorkerProcessOutcome.DEAD_LETTERED
        assert result.job_id == job_id
        assert result.job_status is JobStatus.DEAD_LETTERED
        assert result.error_message is not None
        assert result.error_message.startswith("HandlerExecutionError:")
        assert "always_fail intentionally failed" in result.error_message
        assert queue.pending_count == 0

        async with session_factory() as session:
            stored = await JobRepository(session).get_job_by_id(job_id)
            assert stored is not None
            assert stored.status == JobStatus.DEAD_LETTERED.value
            assert stored.attempts == 1
            assert stored.max_attempts == 1
            assert stored.error_message == result.error_message
            assert stored.lease_owner is None
            assert stored.lease_expires_at is None
            assert stored.finished_at is not None
    finally:
        await engine.dispose()


def test_worker_runtime_truncates_recorded_error_messages(tmp_path: Path) -> None:
    asyncio.run(_exercise_worker_error_truncation(tmp_path))


async def _exercise_worker_error_truncation(tmp_path: Path) -> None:
    engine, session_factory = await _build_sqlite_session_factory(tmp_path)
    try:
        queue = InMemoryJobQueue()
        async with session_scope(session_factory) as session:
            repository = JobRepository(session)
            job = await repository.create_job(
                job_type=JobType.ECHO,
                max_attempts=1,
            )
            job_id = job.id
            await queue.enqueue(job_id)

        config = WorkerRuntimeConfig(
            worker_id="worker-truncation",
            poll_seconds=0.01,
            lease_seconds=60.0,
        )
        service = JobWorkerService(
            session_factory=session_factory,
            queue=queue,
            worker_id=config.worker_id,
            lease_seconds=config.lease_seconds,
            handler_runner=_raise_long_error,
        )
        runtime = WorkerRuntime(service=service, config=config)

        result = await runtime.run_once()

        assert result.outcome is WorkerProcessOutcome.DEAD_LETTERED
        assert result.error_message is not None
        assert len(result.error_message) == MAX_RECORDED_ERROR_MESSAGE_LENGTH
        assert result.error_message.startswith("RuntimeError: ")

        async with session_factory() as session:
            stored = await JobRepository(session).get_job_by_id(job_id)
            assert stored is not None
            assert stored.status == JobStatus.DEAD_LETTERED.value
            assert stored.error_message == result.error_message
    finally:
        await engine.dispose()


async def _raise_long_error(
    job_type: JobType | str,
    payload: JobPayload | None = None,
    *,
    context: JobHandlerContext | None = None,
) -> JobResult:
    _ = job_type, payload, context
    raise RuntimeError("x" * 3000)


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
