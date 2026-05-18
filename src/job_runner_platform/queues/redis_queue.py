from __future__ import annotations

import asyncio
from math import ceil
from typing import Final, Protocol, Self, cast
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import RedisError

from job_runner_platform.domain.jobs import JobId
from job_runner_platform.settings import Settings

DEFAULT_REDIS_QUEUE_NAME: Final[str] = "job_runner:jobs:dispatch"

RedisPayload = str | bytes


class JobQueueError(RuntimeError):
    """Raised when a queue message cannot be safely interpreted."""


class RedisListClient(Protocol):
    """Small Redis client surface used by ``RedisJobQueue``.

    Keeping this protocol narrow hides Redis details from services/workers and
    lets tests supply a fake client without a live Redis server.
    """

    async def lpush(self, name: str, *values: str) -> int:
        """Push one or more values onto the left side of a Redis list."""

    async def rpop(self, name: str) -> RedisPayload | None:
        """Pop one value from the right side of a Redis list."""

    async def brpop(
        self,
        keys: str | list[str],
        timeout: int = 0,
    ) -> tuple[RedisPayload, RedisPayload] | None:
        """Blocking pop one value from the right side of a Redis list."""

    async def ping(self) -> bool:
        """Return whether Redis is reachable."""

    async def aclose(self) -> None:
        """Close the Redis client connection pool."""


class RedisJobQueue:
    """Redis-backed dispatch-signal queue for job IDs.

    The implementation uses a single Redis list. ``LPUSH`` plus ``BRPOP`` gives
    simple FIFO delivery for job ID signals while PostgreSQL remains the source
    of truth. Messages are removed when popped; acknowledgement is therefore a
    no-op. Duplicate signals are expected and safe because consumers must claim
    the job through the repository layer before running it.
    """

    def __init__(
        self,
        redis_client: RedisListClient,
        *,
        queue_name: str = DEFAULT_REDIS_QUEUE_NAME,
    ) -> None:
        if not queue_name:
            raise ValueError("queue_name must not be empty")
        self._redis = redis_client
        self._queue_name = queue_name

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        queue_name: str = DEFAULT_REDIS_QUEUE_NAME,
    ) -> Self:
        """Build a Redis queue from application settings."""

        return cls.from_url(settings.redis_url, queue_name=queue_name)

    @classmethod
    def from_url(
        cls,
        redis_url: str,
        *,
        queue_name: str = DEFAULT_REDIS_QUEUE_NAME,
    ) -> Self:
        """Build a Redis queue from a Redis URL."""

        client = Redis.from_url(redis_url, decode_responses=True)
        return cls(
            redis_client=cast(RedisListClient, client),
            queue_name=queue_name,
        )

    @property
    def queue_name(self) -> str:
        """Return the Redis list key used for dispatch signals."""

        return self._queue_name

    async def enqueue(self, job_id: JobId) -> None:
        """Publish a dispatch signal for a persisted job ID."""

        await self._redis.lpush(self._queue_name, str(job_id))

    async def dequeue(self, *, timeout_seconds: float | None = None) -> JobId | None:
        """Poll the next job ID signal from Redis.

        ``timeout_seconds`` values greater than zero use ``BRPOP``. ``None`` or
        non-positive values perform a non-blocking ``RPOP`` suitable for tests
        and tight polling loops.
        """

        if timeout_seconds is None or timeout_seconds <= 0:
            payload = await self._redis.rpop(self._queue_name)
        else:
            timeout = ceil(timeout_seconds)
            popped = await self._redis.brpop(self._queue_name, timeout=timeout)
            if popped is None:
                return None
            _, payload = popped

        if payload is None:
            return None
        return _payload_to_job_id(payload)

    async def acknowledge(self, job_id: JobId) -> None:
        """Acknowledge a dispatch signal.

        Redis list entries are removed by ``RPOP``/``BRPOP`` before the consumer
        sees them, so there is no additional acknowledgement state to mutate.
        This no-op method keeps the queue interface explicit and lets callers
        safely acknowledge duplicate signals after the database rejects a claim.
        """

        _ = job_id
        await asyncio.sleep(0)

    async def is_ready(self) -> bool:
        """Return whether Redis responds to ``PING``."""

        try:
            return bool(await self._redis.ping())
        except RedisError:
            return False

    async def close(self) -> None:
        """Close the underlying Redis client connection pool."""

        await self._redis.aclose()


def _payload_to_job_id(payload: RedisPayload) -> JobId:
    raw_value = payload.decode("utf-8") if isinstance(payload, bytes) else payload
    try:
        return UUID(raw_value)
    except ValueError as exc:
        message = "queue payload is not a valid job UUID"
        raise JobQueueError(message) from exc
