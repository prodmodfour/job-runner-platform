from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
DEMO_SCRIPT = ROOT_DIR / "scripts" / "demo-smoke.sh"
DEMO_DOC = ROOT_DIR / "docs" / "demo-smoke.md"

REQUIRED_JOB_TYPES = ("echo", "checksum", "fail_once", "always_fail", "sleep")
REQUIRED_STATUSES = ("succeeded", "dead_lettered", "running", "cancelled")
REQUIRED_METRICS = (
    "jobs_created_total",
    "jobs_started_total",
    "jobs_succeeded_total",
    "jobs_failed_total",
    "jobs_retried_total",
    "jobs_dead_lettered_total",
    "jobs_cancelled_total",
    "job_duration_seconds",
)
FORBIDDEN_SCRIPT_SNIPPETS = (
    "eval ",
    "bash -c",
    "sh -c",
    "docker run",
    "subprocess",
    "rm -rf",
    "curl |",
)


def test_demo_smoke_script_exists_and_is_executable() -> None:
    assert DEMO_SCRIPT.is_file()
    assert os.access(DEMO_SCRIPT, os.X_OK)

    text = DEMO_SCRIPT.read_text(encoding="utf-8")
    assert text.startswith("#!/usr/bin/env bash\nset -euo pipefail\n")


def test_demo_smoke_script_covers_required_ticket_flows() -> None:
    text = DEMO_SCRIPT.read_text(encoding="utf-8")

    for job_type in REQUIRED_JOB_TYPES:
        assert f'"job_type":"{job_type}"' in text

    for status in REQUIRED_STATUSES:
        assert status in text

    for metric_name in REQUIRED_METRICS:
        assert metric_name in text

    assert "fail_once_attempts < 2" in text
    assert "always_fail_attempts" in text
    assert "cancel_response" in text


def test_demo_smoke_script_avoids_arbitrary_execution_patterns() -> None:
    text = DEMO_SCRIPT.read_text(encoding="utf-8")

    for forbidden_snippet in FORBIDDEN_SCRIPT_SNIPPETS:
        assert forbidden_snippet not in text

    assert "JOB_RUNNER_DEMO_API_BASE_URL" in text
    assert "JOB_RUNNER_DEMO_API_KEY" in text


def test_demo_smoke_documentation_is_linked_and_public_safe() -> None:
    assert DEMO_DOC.is_file()
    doc_text = DEMO_DOC.read_text(encoding="utf-8").casefold()
    docs_index = (ROOT_DIR / "docs" / "README.md").read_text(encoding="utf-8")
    readme = (ROOT_DIR / "README.md").read_text(encoding="utf-8")

    assert "(demo-smoke.md)" in docs_index
    assert "docs/demo-smoke.md" in readme
    assert "scripts/demo-smoke.sh" in doc_text
    assert "docker compose up --build" in doc_text
    assert "never sends shell commands" in doc_text

    for job_type in REQUIRED_JOB_TYPES:
        assert job_type in doc_text
