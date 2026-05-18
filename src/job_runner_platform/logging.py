from __future__ import annotations

import contextvars
import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

_REQUEST_ID: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "job_runner_request_id",
    default=None,
)

REQUEST_ID_HEADER = "X-Request-ID"


def get_request_id() -> str | None:
    """Return the request ID bound to the current context, if any."""

    return _REQUEST_ID.get()


def set_request_id(request_id: str) -> contextvars.Token[str | None]:
    """Bind a request ID to the current context."""

    return _REQUEST_ID.set(request_id)


def reset_request_id(token: contextvars.Token[str | None]) -> None:
    """Restore the previous request ID context."""

    _REQUEST_ID.reset(token)


class RequestIdLogFilter(logging.Filter):
    """Attach the current request ID to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.__dict__["request_id"] = get_request_id()
        return True


class JsonLogFormatter(logging.Formatter):
    """Render log records as compact structured JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        request_id = getattr(record, "request_id", None)
        if isinstance(request_id, str) and request_id:
            payload["request_id"] = request_id

        if record.exc_info is not None:
            payload["exception"] = self.formatException(record.exc_info)

        if record.stack_info is not None:
            payload["stack"] = self.formatStack(record.stack_info)

        return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def configure_logging(log_level: str) -> None:
    """Configure root logging for JSON output with request ID context."""

    level = logging.getLevelNamesMapping().get(log_level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())
    handler.addFilter(RequestIdLogFilter())

    logging.basicConfig(level=level, handlers=[handler], force=True)
    logging.captureWarnings(True)
