from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from job_runner_platform.database.base import Base
from job_runner_platform.domain.jobs import JobStatus, JobType
from job_runner_platform.queues import InMemoryJobQueue
from job_runner_platform.repositories import JobRepository
from job_runner_platform.services import (
    InvalidJobTypeError,
    JobCancellationConflictError,
    JobService,
)


def test_service_creates_job_gets_it_and_enqueues_dispatch_signal(
    tmp_path: Path,
) -> None:
    asyncio.run(_exercise_service_create_and_get(tmp_path))


async def _exercise_service_create_and_get(tmp_path: Path) -> None:
    engine, session_factory = await _build_sqlite_session_factory(tmp_path)
    try:
        async with session_factory() as session:
            repository = JobRepository(session)
            queue = InMemoryJobQueue()
            service = JobService(repository=repository, queue=queue)

            result = await service.create_job(
                job_type=JobType.ECHO,
                payload={"message": "hello"},
                idempotency_key="demo-key-create",
            )

            assert result.idempotency_replayed is False
            assert result.job.job_type == JobType.ECHO.value
            assert result.job.status == JobStatus.QUEUED.value
            assert result.job.payload == {"message": "hello"}
            assert queue.pending_count == 1
            assert await queue.dequeue(timeout_seconds=0) == result.job.id

            fetched = await service.get_job(result.job.id)
            assert fetched is not None
            assert fetched.id == result.job.id

            missing = await service.get_job(uuid4())
            assert missing is None
    finally:
        await engine.dispose()


def test_service_returns_existing_job_for_idempotency_replay(
    tmp_path: Path,
) -> None:
    asyncio.run(_exercise_service_idempotency_replay(tmp_path))


async def _exercise_service_idempotency_replay(tmp_path: Path) -> None:
    engine, session_factory = await _build_sqlite_session_factory(tmp_path)
    try:
        async with session_factory() as session:
            repository = JobRepository(session)
            queue = InMemoryJobQueue()
            service = JobService(repository=repository, queue=queue)

            first = await service.create_job(
                job_type=JobType.ECHO,
                payload={"message": "original"},
                idempotency_key="demo-key-replay",
            )
            replay = await service.create_job(
                job_type=JobType.SLEEP,
                payload={"seconds": 1},
                idempotency_key="demo-key-replay",
            )

            assert first.idempotency_replayed is False
            assert replay.idempotency_replayed is True
            assert replay.job.id == first.job.id
            assert replay.job.job_type == JobType.ECHO.value
            assert replay.job.payload == {"message": "original"}
            assert queue.pending_count == 1

            jobs = await service.list_jobs(limit=10, offset=0)
            assert jobs.count == 1
    finally:
        await engine.dispose()


def test_service_rejects_invalid_job_type_without_persisting_or_enqueueing(
    tmp_path: Path,
) -> None:
    asyncio.run(_exercise_service_invalid_job_type(tmp_path))


async def _exercise_service_invalid_job_type(tmp_path: Path) -> None:
    engine, session_factory = await _build_sqlite_session_factory(tmp_path)
    try:
        async with session_factory() as session:
            repository = JobRepository(session)
            queue = InMemoryJobQueue()
            service = JobService(repository=repository, queue=queue)

            with pytest.raises(InvalidJobTypeError, match="allowlisted"):
                await service.create_job(
                    job_type="command",
                    payload={"command": "not allowed"},
                )

            jobs = await service.list_jobs(limit=10, offset=0)
            assert jobs.count == 0
            assert queue.pending_count == 0
    finally:
        await engine.dispose()


def test_service_lists_jobs_with_pagination_and_status_filter(
    tmp_path: Path,
) -> None:
    asyncio.run(_exercise_service_list_pagination(tmp_path))


async def _exercise_service_list_pagination(tmp_path: Path) -> None:
    engine, session_factory = await _build_sqlite_session_factory(tmp_path)
    try:
        async with session_factory() as session:
            repository = JobRepository(session)
            queue = InMemoryJobQueue()
            service = JobService(repository=repository, queue=queue)

            created_ids = set()
            for job_type in (JobType.ECHO, JobType.SLEEP, JobType.CHECKSUM):
                created = await service.create_job(job_type=job_type)
                created_ids.add(created.job.id)

            first_page = await service.list_jobs(limit=2, offset=0)
            second_page = await service.list_jobs(limit=2, offset=2)
            queued_page = await service.list_jobs(
                limit=10,
                offset=0,
                status="queued",
            )

            assert first_page.limit == 2
            assert first_page.offset == 0
            assert first_page.count == 2
            assert second_page.limit == 2
            assert second_page.offset == 2
            assert second_page.count == 1
            assert queued_page.count == 3

            paged_ids = {job.id for job in first_page.items + second_page.items}
            assert paged_ids == created_ids
    finally:
        await engine.dispose()


def test_service_cancels_queued_job(tmp_path: Path) -> None:
    asyncio.run(_exercise_service_cancel_queued_job(tmp_path))


async def _exercise_service_cancel_queued_job(tmp_path: Path) -> None:
    engine, session_factory = await _build_sqlite_session_factory(tmp_path)
    try:
        async with session_factory() as session:
            repository = JobRepository(session)
            queue = InMemoryJobQueue()
            service = JobService(repository=repository, queue=queue)
            created = await service.create_job(job_type=JobType.SLEEP)

            cancellation = await service.cancel_job(created.job.id)

            assert cancellation.cancellation_requested is True
            assert cancellation.message == "queued job cancelled"
            assert cancellation.job.status == JobStatus.CANCELLED.value
            assert cancellation.job.finished_at is not None
    finally:
        await engine.dispose()


def test_service_requests_cancellation_for_running_job(tmp_path: Path) -> None:
    asyncio.run(_exercise_service_cancel_running_job(tmp_path))


async def _exercise_service_cancel_running_job(tmp_path: Path) -> None:
    engine, session_factory = await _build_sqlite_session_factory(tmp_path)
    try:
        async with session_factory() as session:
            repository = JobRepository(session)
            queue = InMemoryJobQueue()
            service = JobService(repository=repository, queue=queue)
            created = await service.create_job(job_type=JobType.SLEEP)
            lease_expires_at = datetime.now(UTC) + timedelta(minutes=5)

            claimed = await repository.claim_queued_job(
                job_id=created.job.id,
                worker_id="worker-1",
                lease_expires_at=lease_expires_at,
            )
            assert claimed is not None
            cancellation = await service.cancel_job(created.job.id)

            assert cancellation.cancellation_requested is True
            assert cancellation.message == "cancellation requested"
            assert cancellation.job.status == JobStatus.CANCEL_REQUESTED.value
            assert cancellation.job.lease_owner == "worker-1"
    finally:
        await engine.dispose()


def test_service_rejects_cancellation_for_terminal_job(tmp_path: Path) -> None:
    asyncio.run(_exercise_service_cancel_terminal_job(tmp_path))


async def _exercise_service_cancel_terminal_job(tmp_path: Path) -> None:
    engine, session_factory = await _build_sqlite_session_factory(tmp_path)
    try:
        async with session_factory() as session:
            repository = JobRepository(session)
            queue = InMemoryJobQueue()
            service = JobService(repository=repository, queue=queue)
            created = await service.create_job(job_type=JobType.ECHO)
            lease_expires_at = datetime.now(UTC) + timedelta(minutes=5)

            claimed = await repository.claim_queued_job(
                job_id=created.job.id,
                worker_id="worker-1",
                lease_expires_at=lease_expires_at,
            )
            assert claimed is not None
            completed = await repository.complete_job(job_id=created.job.id)
            assert completed is not None
            assert completed.status == JobStatus.SUCCEEDED.value

            with pytest.raises(JobCancellationConflictError, match="already terminal"):
                await service.cancel_job(created.job.id)
    finally:
        await engine.dispose()


async def _build_sqlite_session_factory(
    tmp_path: Path,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'service.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        autoflush=False,
    )
    return engine, session_factory
