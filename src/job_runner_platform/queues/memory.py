from __future__ import annotations

import asyncio
from collections import deque

from job_runner_platform.domain.jobs import JobId


class InMemoryJobQueue:
    """In-memory queue implementation for fast unit tests.

    This fake intentionally permits duplicate job IDs, matching the Redis
    dispatch-signal model. Duplicate safety belongs to the repository/service
    claim path, which checks PostgreSQL state before running a job.
    """

    def __init__(self, *, ready: bool = True) -> None:
        self._messages: deque[JobId] = deque()
        self._ready = ready

    @property
    def pending_count(self) -> int:
        """Return the number of queued dispatch signals."""

        return len(self._messages)

    def set_ready(self, ready: bool) -> None:
        """Set readiness for tests that need dependency-failure simulation."""

        self._ready = ready

    async def enqueue(self, job_id: JobId) -> None:
        """Publish a dispatch signal for a persisted job ID."""

        self._messages.append(job_id)
        await asyncio.sleep(0)

    async def dequeue(self, *, timeout_seconds: float | None = None) -> JobId | None:
        """Return the next job ID signal, or ``None`` when empty."""

        _ = timeout_seconds
        await asyncio.sleep(0)
        if not self._messages:
            return None
        return self._messages.popleft()

    async def acknowledge(self, job_id: JobId) -> None:
        """Acknowledge a dispatch signal.

        The fake has no in-flight state, so acknowledgement is intentionally a
        no-op just like the Redis list implementation after a successful pop.
        """

        _ = job_id
        await asyncio.sleep(0)

    async def is_ready(self) -> bool:
        """Return configured readiness for this fake queue."""

        await asyncio.sleep(0)
        return self._ready
