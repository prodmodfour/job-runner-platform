from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Self

from job_runner_platform.services.worker import JobWorkerService, WorkerProcessResult
from job_runner_platform.settings import Settings


@dataclass(frozen=True, slots=True)
class WorkerRuntimeConfig:
    """Runtime configuration for a worker process."""

    worker_id: str
    poll_seconds: float
    lease_seconds: float

    def __post_init__(self) -> None:
        if not self.worker_id:
            raise ValueError("worker_id must not be empty")
        if self.poll_seconds <= 0:
            raise ValueError("poll_seconds must be greater than 0")
        if self.lease_seconds <= 0:
            raise ValueError("lease_seconds must be greater than 0")

    @classmethod
    def from_settings(cls, settings: Settings) -> Self:
        """Build worker runtime configuration from environment-backed settings."""

        return cls(
            worker_id=settings.worker_id,
            poll_seconds=settings.job_poll_seconds,
            lease_seconds=settings.job_lease_seconds,
        )


class WorkerRuntime:
    """Long-running worker loop around ``JobWorkerService``."""

    def __init__(
        self,
        *,
        service: JobWorkerService,
        config: WorkerRuntimeConfig,
        logger: logging.Logger | None = None,
    ) -> None:
        self._service = service
        self._config = config
        self._logger = logger or logging.getLogger(__name__)

    async def run_once(self) -> WorkerProcessResult:
        """Process at most one queue dispatch signal."""

        return await self._service.process_one_job(
            timeout_seconds=self._config.poll_seconds,
        )

    async def run_until_stopped(self, stop_event: asyncio.Event) -> None:
        """Run until ``stop_event`` is set.

        Shutdown is cooperative: the worker checks the event between jobs. If a
        handler is already running, the worker lets that safe handler finish and
        persists the outcome before exiting.
        """

        self._logger.info(
            "worker started",
            extra={
                "worker_id": self._config.worker_id,
                "poll_seconds": self._config.poll_seconds,
                "lease_seconds": self._config.lease_seconds,
            },
        )
        try:
            while not stop_event.is_set():
                await self.run_once()
        finally:
            self._logger.info(
                "worker stopped",
                extra={"worker_id": self._config.worker_id},
            )
