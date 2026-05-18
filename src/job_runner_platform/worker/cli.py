from __future__ import annotations

import argparse
import asyncio
import logging
import signal
from collections.abc import Sequence
from types import FrameType

from job_runner_platform.database.session import (
    build_async_engine,
    build_async_sessionmaker,
)
from job_runner_platform.logging import configure_logging
from job_runner_platform.observability import (
    MetricsHttpServer,
    start_metrics_http_server,
)
from job_runner_platform.queues import RedisJobQueue
from job_runner_platform.services.worker import JobWorkerService
from job_runner_platform.settings import Settings, get_settings
from job_runner_platform.worker.runtime import WorkerRuntime, WorkerRuntimeConfig


def main(argv: Sequence[str] | None = None) -> int:
    """Run the worker CLI."""

    parser = argparse.ArgumentParser(
        description=(
            "Run the job-runner-platform worker for safe allowlisted demo jobs."
        ),
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="process at most one dispatch signal and exit",
    )
    args = parser.parse_args(argv)
    return asyncio.run(_run_worker(run_once=bool(args.once), settings=get_settings()))


async def _run_worker(*, run_once: bool, settings: Settings) -> int:
    configure_logging(settings.log_level)
    config = WorkerRuntimeConfig.from_settings(settings)
    engine = build_async_engine(settings)
    session_factory = build_async_sessionmaker(engine)
    queue = RedisJobQueue.from_settings(settings)
    service = JobWorkerService(
        session_factory=session_factory,
        queue=queue,
        worker_id=config.worker_id,
        lease_seconds=config.lease_seconds,
    )
    runtime = WorkerRuntime(service=service, config=config)
    metrics_server: MetricsHttpServer | None = None

    try:
        if settings.worker_metrics_enabled:
            metrics_server = start_metrics_http_server(
                host=settings.worker_metrics_host,
                port=settings.worker_metrics_port,
            )
            logging.getLogger(__name__).info(
                "worker metrics server started",
                extra={
                    "worker_id": config.worker_id,
                    "metrics_host": settings.worker_metrics_host,
                    "metrics_port": metrics_server.port,
                },
            )
        if run_once:
            await runtime.run_once()
        else:
            stop_event = asyncio.Event()
            _install_signal_handlers(stop_event)
            await runtime.run_until_stopped(stop_event)
    finally:
        if metrics_server is not None:
            metrics_server.shutdown()
        await queue.close()
        await engine.dispose()

    return 0


def _install_signal_handlers(stop_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()

    def request_stop() -> None:
        stop_event.set()

    def handle_signal(_signum: int, _frame: FrameType | None) -> None:
        request_stop()

    for handled_signal in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(handled_signal, request_stop)
        except (NotImplementedError, RuntimeError):
            try:
                signal.signal(handled_signal, handle_signal)
            except ValueError:
                # Signal registration is only available from the main thread.
                # If unavailable, normal process termination still applies.
                continue


if __name__ == "__main__":
    raise SystemExit(main())
