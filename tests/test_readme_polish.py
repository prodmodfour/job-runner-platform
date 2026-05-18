from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"

REQUIRED_HEADINGS = (
    "# Job Runner Platform",
    "## Portfolio framing",
    "## Implemented scope",
    "## Public-safety constraints",
    "## Out of scope",
    "## Requirements",
    "## Quick start",
    "## Configuration",
    "## API surface",
    "## Worker instructions",
    "## Observability",
    "## Testing and quality gates",
    "## Architecture and documentation links",
    "## Limitations",
)

FIRST_SCREEN_SIGNALS = (
    "fastapi",
    "postgresql",
    "redis",
    "worker",
    "prometheus",
    "portfolio",
    "no arbitrary shell command execution",
)

REQUIRED_ENVIRONMENT_VARIABLES = (
    "JOB_RUNNER_APP_NAME",
    "JOB_RUNNER_APP_VERSION",
    "JOB_RUNNER_ENVIRONMENT",
    "JOB_RUNNER_LOG_LEVEL",
    "JOB_RUNNER_DOCS_ENABLED",
    "JOB_RUNNER_AUTH_ENABLED",
    "JOB_RUNNER_AUTH_API_KEYS",
    "JOB_RUNNER_DATABASE_URL",
    "JOB_RUNNER_REDIS_URL",
    "JOB_RUNNER_WORKER_ID",
    "JOB_RUNNER_JOB_LEASE_SECONDS",
    "JOB_RUNNER_JOB_POLL_SECONDS",
    "JOB_RUNNER_WORKER_METRICS_ENABLED",
    "JOB_RUNNER_WORKER_METRICS_HOST",
    "JOB_RUNNER_WORKER_METRICS_PORT",
)

REQUIRED_ENDPOINTS = (
    "GET /healthz",
    "GET /readyz",
    "GET /metrics",
    "POST /jobs",
    "GET /jobs",
    "GET /jobs/{job_id}",
    "POST /jobs/{job_id}/cancel",
)

REQUIRED_DOCUMENTATION_LINKS = (
    "docs/architecture.md",
    "docs/api-walkthrough.md",
    "docs/operations.md",
    "docs/runbook.md",
    "docs/job-handlers.md",
    "docs/observability.md",
    "docs/demo-smoke.md",
    "docs/decisions/README.md",
)


def _read_readme() -> str:
    return README.read_text(encoding="utf-8")


def test_final_readme_contains_ticket_023_sections() -> None:
    text = _read_readme()

    for heading in REQUIRED_HEADINGS:
        assert heading in text, f"README is missing {heading!r}"


def test_readme_first_screen_sells_portfolio_value() -> None:
    first_screen = "\n".join(_read_readme().splitlines()[:32]).casefold()

    for signal in FIRST_SCREEN_SIGNALS:
        assert signal in first_screen, f"first README screen is missing {signal!r}"


def test_readme_documents_configuration_and_api_surface() -> None:
    text = _read_readme()

    for variable in REQUIRED_ENVIRONMENT_VARIABLES:
        assert variable in text, f"README does not document {variable}"

    assert "max_attempts" in text

    for endpoint in REQUIRED_ENDPOINTS:
        assert endpoint in text, f"README does not document {endpoint}"


def test_readme_links_core_architecture_and_operations_docs() -> None:
    text = _read_readme()

    for link in REQUIRED_DOCUMENTATION_LINKS:
        assert link in text, f"README does not link {link}"


def test_readme_reiterates_public_safety_boundaries() -> None:
    text = _read_readme().casefold()

    for phrase in (
        "independent public portfolio project",
        "must not run arbitrary user-submitted commands",
        "subprocesses",
        "safe built-in demo handlers",
    ):
        assert phrase in text
