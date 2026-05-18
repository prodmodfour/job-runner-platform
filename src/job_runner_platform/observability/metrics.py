from __future__ import annotations

from typing import Final, Protocol

from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram
from prometheus_client.exposition import generate_latest

PROMETHEUS_REGISTRY: Final[CollectorRegistry] = CollectorRegistry(auto_describe=True)
METRICS_CONTENT_TYPE: Final[str] = CONTENT_TYPE_LATEST

_JOBS_CREATED: Final[Counter] = Counter(
    "jobs_created",
    "Total jobs created through the API service layer.",
    registry=PROMETHEUS_REGISTRY,
)
_JOBS_STARTED: Final[Counter] = Counter(
    "jobs_started",
    "Total jobs claimed and started by workers.",
    registry=PROMETHEUS_REGISTRY,
)
_JOBS_SUCCEEDED: Final[Counter] = Counter(
    "jobs_succeeded",
    "Total jobs completed successfully by workers.",
    registry=PROMETHEUS_REGISTRY,
)
_JOBS_FAILED: Final[Counter] = Counter(
    "jobs_failed",
    "Total failed handler attempts recorded by workers.",
    registry=PROMETHEUS_REGISTRY,
)
_JOBS_RETRIED: Final[Counter] = Counter(
    "jobs_retried",
    "Total jobs requeued for another attempt.",
    registry=PROMETHEUS_REGISTRY,
)
_JOBS_DEAD_LETTERED: Final[Counter] = Counter(
    "jobs_dead_lettered",
    "Total jobs moved to the dead-letter terminal state.",
    registry=PROMETHEUS_REGISTRY,
)
_JOBS_CANCELLED: Final[Counter] = Counter(
    "jobs_cancelled",
    "Total jobs moved to the cancelled terminal state.",
    registry=PROMETHEUS_REGISTRY,
)
_JOB_DURATION_SECONDS: Final[Histogram] = Histogram(
    "job_duration_seconds",
    "Duration in seconds spent processing claimed jobs.",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=PROMETHEUS_REGISTRY,
)
_API_REQUESTS: Final[Counter] = Counter(
    "api_requests",
    "Total HTTP requests handled by the API.",
    labelnames=("method", "path", "status_code"),
    registry=PROMETHEUS_REGISTRY,
)
_API_REQUEST_DURATION_SECONDS: Final[Histogram] = Histogram(
    "api_request_duration_seconds",
    "HTTP request duration in seconds.",
    labelnames=("method", "path", "status_code"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=PROMETHEUS_REGISTRY,
)
_WORKER_POLLS: Final[Counter] = Counter(
    "worker_polls",
    "Total worker polling cycles by outcome.",
    labelnames=("outcome",),
    registry=PROMETHEUS_REGISTRY,
)
_QUEUE_POLLS: Final[Counter] = Counter(
    "queue_polls",
    "Total worker queue polls by result.",
    labelnames=("result",),
    registry=PROMETHEUS_REGISTRY,
)


class MetricsRecorder(Protocol):
    """Application metrics sink used by services, workers, and middleware."""

    def record_job_created(self) -> None:
        """Record that a new job row and dispatch signal were created."""

    def record_job_started(self) -> None:
        """Record that a worker claimed and started a job."""

    def record_job_succeeded(self) -> None:
        """Record that a job reached the succeeded terminal state."""

    def record_job_failed(self) -> None:
        """Record a failed handler attempt."""

    def record_job_retried(self) -> None:
        """Record that a job was requeued for another attempt."""

    def record_job_dead_lettered(self) -> None:
        """Record that a job reached the dead-letter terminal state."""

    def record_job_cancelled(self) -> None:
        """Record that a job reached the cancelled terminal state."""

    def record_job_duration(self, duration_seconds: float) -> None:
        """Observe worker processing duration for a claimed job."""

    def record_api_request(
        self,
        *,
        method: str,
        path: str,
        status_code: int,
        duration_seconds: float,
    ) -> None:
        """Record one HTTP request handled by the API."""

    def record_worker_poll(self, *, outcome: str) -> None:
        """Record one worker polling cycle outcome."""

    def record_queue_poll(self, *, message_received: bool) -> None:
        """Record whether a worker queue poll returned a dispatch signal."""


class PrometheusMetricsRecorder:
    """Prometheus-backed implementation of the metrics recorder protocol."""

    def record_job_created(self) -> None:
        _JOBS_CREATED.inc()

    def record_job_started(self) -> None:
        _JOBS_STARTED.inc()

    def record_job_succeeded(self) -> None:
        _JOBS_SUCCEEDED.inc()

    def record_job_failed(self) -> None:
        _JOBS_FAILED.inc()

    def record_job_retried(self) -> None:
        _JOBS_RETRIED.inc()

    def record_job_dead_lettered(self) -> None:
        _JOBS_DEAD_LETTERED.inc()

    def record_job_cancelled(self) -> None:
        _JOBS_CANCELLED.inc()

    def record_job_duration(self, duration_seconds: float) -> None:
        _JOB_DURATION_SECONDS.observe(max(duration_seconds, 0.0))

    def record_api_request(
        self,
        *,
        method: str,
        path: str,
        status_code: int,
        duration_seconds: float,
    ) -> None:
        labels = {
            "method": method,
            "path": path,
            "status_code": str(status_code),
        }
        _API_REQUESTS.labels(**labels).inc()
        _API_REQUEST_DURATION_SECONDS.labels(**labels).observe(
            max(duration_seconds, 0.0),
        )

    def record_worker_poll(self, *, outcome: str) -> None:
        _WORKER_POLLS.labels(outcome=outcome).inc()

    def record_queue_poll(self, *, message_received: bool) -> None:
        result = "message" if message_received else "empty"
        _QUEUE_POLLS.labels(result=result).inc()


_METRICS_RECORDER: Final[MetricsRecorder] = PrometheusMetricsRecorder()


def get_metrics_recorder() -> MetricsRecorder:
    """Return the process-global metrics recorder."""

    return _METRICS_RECORDER


def render_metrics() -> bytes:
    """Render the current Prometheus exposition payload."""

    return generate_latest(PROMETHEUS_REGISTRY)
