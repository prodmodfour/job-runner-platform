from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from job_runner_platform.database.base import Base
from job_runner_platform.domain.jobs import JobStatus, JobType
from job_runner_platform.queues import InMemoryJobQueue, RedisJobQueue
from job_runner_platform.queues.redis_queue import RedisPayload
from job_runner_platform.repositories import JobRepository


def test_in_memory_queue_enqueues_dequeues_acknowledges_and_reports_ready() -> None:
    asyncio.run(_exercise_in_memory_queue())


async def _exercise_in_memory_queue() -> None:
    queue = InMemoryJobQueue()
    first_job_id = uuid4()
    second_job_id = uuid4()

    assert await queue.is_ready() is True
    assert queue.pending_count == 0

    await queue.enqueue(first_job_id)
    await queue.enqueue(second_job_id)

    assert queue.pending_count == 2
    assert await queue.dequeue(timeout_seconds=0) == first_job_id
    await queue.acknowledge(first_job_id)
    assert await queue.dequeue(timeout_seconds=0) == second_job_id
    assert await queue.dequeue(timeout_seconds=0) is None

    queue.set_ready(False)
    assert await queue.is_ready() is False


def test_redis_queue_serializes_job_ids_and_exposes_readiness() -> None:
    asyncio.run(_exercise_redis_queue_with_fake_client())


async def _exercise_redis_queue_with_fake_client() -> None:
    redis_client = FakeRedisListClient()
    queue = RedisJobQueue(redis_client, queue_name="test:jobs")
    first_job_id = uuid4()
    second_job_id = uuid4()

    await queue.enqueue(first_job_id)
    await queue.enqueue(second_job_id)

    assert redis_client.list_name == "test:jobs"
    assert await queue.dequeue(timeout_seconds=1) == first_job_id
    await queue.acknowledge(first_job_id)
    assert await queue.dequeue(timeout_seconds=0) == second_job_id
    assert await queue.dequeue(timeout_seconds=0) is None
    assert await queue.is_ready() is True

    redis_client.ready = False
    assert await queue.is_ready() is False

    await queue.close()
    assert redis_client.closed is True


def test_duplicate_queue_messages_are_safe_when_database_claim_checks_state(
    tmp_path: Path,
) -> None:
    asyncio.run(_exercise_duplicate_signal_safety(tmp_path))


async def _exercise_duplicate_signal_safety(tmp_path: Path) -> None:
    engine, session_factory = await _build_sqlite_session_factory(tmp_path)
    try:
        async with session_factory() as session:
            repository = JobRepository(session)
            queue = InMemoryJobQueue()
            job = await repository.create_job(job_type=JobType.ECHO)
            lease_expires_at = datetime.now(UTC) + timedelta(minutes=5)

            await queue.enqueue(job.id)
            await queue.enqueue(job.id)

            first_signal = await queue.dequeue(timeout_seconds=0)
            assert first_signal == job.id
            claimed = await repository.claim_queued_job(
                job_id=job.id,
                worker_id="worker-1",
                lease_expires_at=lease_expires_at,
            )
            assert claimed is not None
            assert claimed.status == JobStatus.RUNNING.value
            assert claimed.attempts == 1
            await queue.acknowledge(job.id)

            duplicate_signal = await queue.dequeue(timeout_seconds=0)
            assert duplicate_signal == job.id
            duplicate_claim = await repository.claim_queued_job(
                job_id=job.id,
                worker_id="worker-2",
                lease_expires_at=lease_expires_at + timedelta(minutes=5),
            )
            assert duplicate_claim is None
            await queue.acknowledge(job.id)

            stored = await repository.get_job_by_id(job.id)
            assert stored is not None
            assert stored.status == JobStatus.RUNNING.value
            assert stored.lease_owner == "worker-1"
            assert stored.attempts == 1
            assert await queue.dequeue(timeout_seconds=0) is None
    finally:
        await engine.dispose()


class FakeRedisListClient:
    def __init__(self) -> None:
        self.messages: list[str] = []
        self.list_name: str | None = None
        self.ready = True
        self.closed = False

    async def lpush(self, name: str, *values: str) -> int:
        self.list_name = name
        self.messages = [*values, *self.messages]
        await asyncio.sleep(0)
        return len(self.messages)

    async def rpop(self, name: str) -> RedisPayload | None:
        self.list_name = name
        await asyncio.sleep(0)
        if not self.messages:
            return None
        return self.messages.pop()

    async def brpop(
        self,
        keys: str | list[str],
        timeout: int = 0,
    ) -> tuple[RedisPayload, RedisPayload] | None:
        _ = timeout
        name = keys if isinstance(keys, str) else keys[0]
        payload = await self.rpop(name)
        if payload is None:
            return None
        return name, payload

    async def ping(self) -> bool:
        await asyncio.sleep(0)
        return self.ready

    async def aclose(self) -> None:
        await asyncio.sleep(0)
        self.closed = True


async def _build_sqlite_session_factory(
    tmp_path: Path,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'queue.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        autoflush=False,
    )
    return engine, session_factory
