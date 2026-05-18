from __future__ import annotations

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
CI_WORKFLOW = ROOT_DIR / ".github" / "workflows" / "ci.yml"


def test_ci_workflow_exists_and_uses_python_312_with_uv() -> None:
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "name: CI" in workflow
    assert "actions/checkout@v4" in workflow
    assert "astral-sh/setup-uv@v5" in workflow
    assert "actions/setup-python@v5" in workflow
    assert 'python-version: "3.12"' in workflow
    assert "uv sync --locked --all-groups" in workflow


def test_ci_workflow_runs_required_quality_commands() -> None:
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    for command in (
        "bash -n",
        "uv run ruff check .",
        "uv run ruff format --check .",
        "uv run mypy src tests",
        "docker compose config",
        "uv run alembic upgrade head",
        "uv run pytest --cov=job_runner_platform --cov-report=term-missing",
    ):
        assert command in workflow


def test_ci_workflow_includes_postgres_and_optional_guardrail_steps() -> None:
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "postgres:16-alpine" in workflow
    assert "POSTGRES_DB: job_runner" in workflow
    assert "POSTGRES_USER: job_runner" in workflow
    assert "POSTGRES_PASSWORD: job_runner" in workflow
    assert "pg_isready -U job_runner -d job_runner" in workflow
    assert (
        "JOB_RUNNER_DATABASE_URL: "
        "postgresql+asyncpg://job_runner:job_runner@localhost:5432/job_runner"
        in workflow
    )
    assert "Run public-safety guardrail if present" in workflow
    assert "scripts/check-public-safety.sh" in workflow
    assert "Run architecture guardrail if present" in workflow
    assert "scripts/check-architecture-boundaries.sh" in workflow
