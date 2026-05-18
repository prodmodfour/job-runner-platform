from __future__ import annotations

from typing import Protocol

from job_runner_platform.domain.jobs import JobId


class JobQueue(Protocol):
    """Dispatch-signal queue abstraction for job IDs.

    PostgreSQL remains the source of truth for job state. Queue implementations
    only transport job IDs as wake-up signals for future services/workers.
    Consumers must still claim jobs through the repository layer so duplicate
    messages are safely ignored when the database row is no longer queued.
    """

    async def enqueue(self, job_id: JobId) -> None:
        """Publish a dispatch signal for a persisted job ID."""

    async def dequeue(self, *, timeout_seconds: float | None = None) -> JobId | None:
        """Poll for the next job ID signal, returning ``None`` on timeout/empty."""

    async def acknowledge(self, job_id: JobId) -> None:
        """Acknowledge or safely ignore a processed dispatch signal."""

    async def is_ready(self) -> bool:
        """Return whether the queue dependency is reachable."""
