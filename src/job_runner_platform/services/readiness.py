from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Protocol

from job_runner_platform.queues import JobQueue

POSTGRESQL_CHECK_NAME: Final[str] = "postgresql"
REDIS_CHECK_NAME: Final[str] = "redis"
POSTGRESQL_FAILURE_MESSAGE: Final[str] = "PostgreSQL readiness query failed"
REDIS_FAILURE_MESSAGE: Final[str] = "Redis readiness ping failed"


class ReadinessCheck(Protocol):
    """Callable dependency probe used by the readiness service."""

    async def __call__(self) -> None:
        """Complete successfully only when the dependency is ready."""


@dataclass(frozen=True, slots=True)
class DependencyReadinessResult:
    """Readiness result for one dependency."""

    name: str
    ready: bool
    message: str | None = None


@dataclass(frozen=True, slots=True)
class ReadinessResult:
    """Combined readiness state for the API process dependencies."""

    checks: tuple[DependencyReadinessResult, ...]

    @property
    def is_ready(self) -> bool:
        """Return whether every dependency check succeeded."""

        return all(check.ready for check in self.checks)


class QueueReadinessCheck:
    """Queue readiness probe using the queue abstraction instead of Redis calls."""

    def __init__(self, queue: JobQueue) -> None:
        self._queue = queue

    async def __call__(self) -> None:
        """Raise ``QueueReadinessError`` when Redis is unavailable."""

        if not await self._queue.is_ready():
            raise QueueReadinessError


class QueueReadinessError(RuntimeError):
    """Raised when the dispatch queue readiness check fails."""


class ReadinessService:
    """Business service for API readiness checks.

    The service coordinates dependency probes while keeping routes free of
    database queries and Redis calls. PostgreSQL is checked through a database
    layer probe, while Redis is checked through the queue abstraction.
    """

    def __init__(
        self,
        *,
        database_check: ReadinessCheck,
        queue_check: ReadinessCheck,
    ) -> None:
        self._database_check = database_check
        self._queue_check = queue_check

    async def check(self) -> ReadinessResult:
        """Run PostgreSQL and Redis readiness checks."""

        checks = (
            await self._run_check(
                name=POSTGRESQL_CHECK_NAME,
                check=self._database_check,
                failure_message=POSTGRESQL_FAILURE_MESSAGE,
            ),
            await self._run_check(
                name=REDIS_CHECK_NAME,
                check=self._queue_check,
                failure_message=REDIS_FAILURE_MESSAGE,
            ),
        )
        return ReadinessResult(checks=checks)

    async def _run_check(
        self,
        *,
        name: str,
        check: ReadinessCheck,
        failure_message: str,
    ) -> DependencyReadinessResult:
        try:
            await check()
        except Exception:
            return DependencyReadinessResult(
                name=name,
                ready=False,
                message=failure_message,
            )
        return DependencyReadinessResult(name=name, ready=True)
