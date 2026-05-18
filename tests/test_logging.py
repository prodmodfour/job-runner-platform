from __future__ import annotations

import json
import logging

from job_runner_platform.logging import (
    JsonLogFormatter,
    RequestIdLogFilter,
    reset_request_id,
    set_request_id,
)


def test_json_log_formatter_emits_structured_record_with_request_id() -> None:
    token = set_request_id("log-test-request-id")
    try:
        record = logging.LogRecord(
            name="job_runner_platform.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=10,
            msg="health check passed",
            args=(),
            exc_info=None,
        )
        record.__dict__["job_id"] = "job-001"
        RequestIdLogFilter().filter(record)
        payload = json.loads(JsonLogFormatter().format(record))
    finally:
        reset_request_id(token)

    assert payload["level"] == "INFO"
    assert payload["logger"] == "job_runner_platform.test"
    assert payload["message"] == "health check passed"
    assert payload["request_id"] == "log-test-request-id"
    assert payload["job_id"] == "job-001"
    assert "timestamp" in payload
