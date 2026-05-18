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
from job_runner_platform.repositories import JobRepository


def test_repository_creates_gets_lists_and_finds_jobs(tmp_path: Path) -> None:
    asyncio.run(_exercise_repository_creates_gets_lists_and_finds_jobs(tmp_path))


async def _exercise_repository_creates_gets_lists_and_finds_jobs(
    tmp_path: Path,
) -> None:
    engine, session_factory = await _build_sqlite_session_factory(tmp_path)
    try:
        async with session_factory() as session:
            repository = JobRepository(session)

            first = await repository.create_job(
                job_type=JobType.ECHO,
                payload={"message": "hello"},
                idempotency_key="demo-key-001",
            )
            second = await repository.create_job(
                job_type=JobType.SLEEP,
                payload={"seconds": 1},
                priority=5,
                max_attempts=4,
            )

            fetched = await repository.get_job_by_id(first.id)
            assert fetched is not None
            assert fetched.id == first.id
            assert fetched.job_type == JobType.ECHO.value
            assert fetched.status == JobStatus.QUEUED.value
            assert fetched.payload == {"message": "hello"}
            assert fetched.attempts == 0
            assert fetched.max_attempts == 3

            idempotent = await repository.find_by_idempotency_key("demo-key-001")
            assert idempotent is not None
            assert idempotent.id == first.id

            missing = await repository.find_by_idempotency_key("missing-key")
            assert missing is None

            all_jobs = await repository.list_jobs(limit=10, offset=0)
            assert {job.id for job in all_jobs} == {first.id, second.id}

            queued_jobs = await repository.list_jobs(
                limit=10,
                offset=0,
                status=JobStatus.QUEUED,
            )
            assert {job.id for job in queued_jobs} == {first.id, second.id}

            paged_jobs = await repository.list_jobs(limit=1, offset=1)
            assert len(paged_jobs) == 1
    finally:
        await engine.dispose()


def test_repository_claims_queued_job_and_rejects_duplicate_claim(
    tmp_path: Path,
) -> None:
    asyncio.run(_exercise_repository_claims_queued_job(tmp_path))


async def _exercise_repository_claims_queued_job(tmp_path: Path) -> None:
    engine, session_factory = await _build_sqlite_session_factory(tmp_path)
    try:
        async with session_factory() as session:
            repository = JobRepository(session)
            job = await repository.create_job(job_type=JobType.ECHO)
            lease_expires_at = datetime.now(UTC) + timedelta(minutes=5)

            claimed = await repository.claim_queued_job(
                job_id=job.id,
                worker_id="worker-1",
                lease_expires_at=lease_expires_at,
            )

            assert claimed is not None
            assert claimed.id == job.id
            assert claimed.status == JobStatus.RUNNING.value
            assert claimed.attempts == 1
            assert claimed.started_at is not None
            assert claimed.finished_at is None
            assert claimed.lease_owner == "worker-1"
            assert claimed.lease_expires_at == lease_expires_at

            duplicate = await repository.claim_queued_job(
                job_id=job.id,
                worker_id="worker-2",
                lease_expires_at=lease_expires_at + timedelta(minutes=5),
            )
            assert duplicate is None

            with pytest.raises(ValueError, match="lease_expires_at"):
                await repository.claim_queued_job(
                    job_id=job.id,
                    worker_id="worker-3",
                    lease_expires_at=datetime(2026, 1, 1, 0, 0, 0),
                )
    finally:
        await engine.dispose()


def test_repository_records_completion_failure_requeue_and_dead_letter(
    tmp_path: Path,
) -> None:
    asyncio.run(_exercise_repository_lifecycle_transitions(tmp_path))


async def _exercise_repository_lifecycle_transitions(tmp_path: Path) -> None:
    engine, session_factory = await _build_sqlite_session_factory(tmp_path)
    try:
        async with session_factory() as session:
            repository = JobRepository(session)
            lease_expires_at = datetime.now(UTC) + timedelta(minutes=5)

            successful_job = await repository.create_job(job_type=JobType.ECHO)
            await repository.claim_queued_job(
                job_id=successful_job.id,
                worker_id="worker-1",
                lease_expires_at=lease_expires_at,
            )
            completed = await repository.complete_job(
                job_id=successful_job.id,
                result={"echoed": True},
            )
            assert completed is not None
            assert completed.status == JobStatus.SUCCEEDED.value
            assert completed.result == {"echoed": True}
            assert completed.error_message is None
            assert completed.lease_owner is None
            assert completed.lease_expires_at is None
            assert completed.finished_at is not None

            failed_job = await repository.create_job(job_type=JobType.ALWAYS_FAIL)
            await repository.claim_queued_job(
                job_id=failed_job.id,
                worker_id="worker-1",
                lease_expires_at=lease_expires_at,
            )
            failed = await repository.fail_job(
                job_id=failed_job.id,
                error_message="demo failure",
            )
            assert failed is not None
            assert failed.status == JobStatus.FAILED.value
            assert failed.error_message == "demo failure"
            assert failed.lease_owner is None
            assert failed.finished_at is not None

            requeued = await repository.requeue_job(
                job_id=failed_job.id,
                error_message="retry scheduled",
            )
            assert requeued is not None
            assert requeued.status == JobStatus.QUEUED.value
            assert requeued.attempts == 1
            assert requeued.error_message == "retry scheduled"
            assert requeued.started_at is None
            assert requeued.finished_at is None

            claimed_again = await repository.claim_queued_job(
                job_id=failed_job.id,
                worker_id="worker-2",
                lease_expires_at=lease_expires_at + timedelta(minutes=5),
            )
            assert claimed_again is not None
            assert claimed_again.attempts == 2

            dead_lettered = await repository.mark_dead_lettered(
                job_id=failed_job.id,
                error_message="max attempts reached",
            )
            assert dead_lettered is not None
            assert dead_lettered.status == JobStatus.DEAD_LETTERED.value
            assert dead_lettered.error_message == "max attempts reached"
            assert dead_lettered.lease_owner is None
            assert dead_lettered.finished_at is not None

            cannot_fail_terminal = await repository.fail_job(
                job_id=successful_job.id,
                error_message="should not change terminal job",
            )
            assert cannot_fail_terminal is None
    finally:
        await engine.dispose()


def test_repository_requests_cancellation_for_queued_and_running_jobs(
    tmp_path: Path,
) -> None:
    asyncio.run(_exercise_repository_cancellation(tmp_path))


async def _exercise_repository_cancellation(tmp_path: Path) -> None:
    engine, session_factory = await _build_sqlite_session_factory(tmp_path)
    try:
        async with session_factory() as session:
            repository = JobRepository(session)
            lease_expires_at = datetime.now(UTC) + timedelta(minutes=5)

            queued_job = await repository.create_job(job_type=JobType.SLEEP)
            cancelled = await repository.request_cancellation(queued_job.id)
            assert cancelled is not None
            assert cancelled.status == JobStatus.CANCELLED.value
            assert cancelled.finished_at is not None

            cannot_claim_cancelled = await repository.claim_queued_job(
                job_id=queued_job.id,
                worker_id="worker-1",
                lease_expires_at=lease_expires_at,
            )
            assert cannot_claim_cancelled is None

            running_job = await repository.create_job(job_type=JobType.SLEEP)
            await repository.claim_queued_job(
                job_id=running_job.id,
                worker_id="worker-1",
                lease_expires_at=lease_expires_at,
            )
            cancellation_requested = await repository.request_cancellation(
                running_job.id,
            )
            assert cancellation_requested is not None
            assert cancellation_requested.status == JobStatus.CANCEL_REQUESTED.value
            assert cancellation_requested.lease_owner == "worker-1"

            terminal_job = await repository.create_job(job_type=JobType.ECHO)
            await repository.claim_queued_job(
                job_id=terminal_job.id,
                worker_id="worker-1",
                lease_expires_at=lease_expires_at,
            )
            await repository.complete_job(job_id=terminal_job.id)
            unchanged = await repository.request_cancellation(terminal_job.id)
            assert unchanged is not None
            assert unchanged.status == JobStatus.SUCCEEDED.value

            missing = await repository.request_cancellation(uuid4())
            assert missing is None
    finally:
        await engine.dispose()


def test_repository_finds_stale_leased_jobs(tmp_path: Path) -> None:
    asyncio.run(_exercise_repository_finds_stale_leased_jobs(tmp_path))


async def _exercise_repository_finds_stale_leased_jobs(tmp_path: Path) -> None:
    engine, session_factory = await _build_sqlite_session_factory(tmp_path)
    try:
        async with session_factory() as session:
            repository = JobRepository(session)
            now = datetime.now(UTC)
            expired_job = await repository.create_job(job_type=JobType.ECHO)
            active_job = await repository.create_job(job_type=JobType.ECHO)
            queued_job = await repository.create_job(job_type=JobType.ECHO)

            await repository.claim_queued_job(
                job_id=expired_job.id,
                worker_id="worker-1",
                lease_expires_at=now - timedelta(seconds=1),
            )
            await repository.claim_queued_job(
                job_id=active_job.id,
                worker_id="worker-2",
                lease_expires_at=now + timedelta(minutes=5),
            )

            stale_jobs = await repository.find_stale_leased_jobs(as_of=now, limit=10)
            assert [job.id for job in stale_jobs] == [expired_job.id]

            assert queued_job.status == JobStatus.QUEUED.value
            with pytest.raises(ValueError, match="as_of"):
                await repository.find_stale_leased_jobs(
                    as_of=datetime(2026, 1, 1, 0, 0, 0),
                )
    finally:
        await engine.dispose()


async def _build_sqlite_session_factory(
    tmp_path: Path,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'repository.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        autoflush=False,
    )
    return engine, session_factory
