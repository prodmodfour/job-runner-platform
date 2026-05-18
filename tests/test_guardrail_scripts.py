from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
PUBLIC_SAFETY_SCRIPT = ROOT_DIR / "scripts" / "check-public-safety.sh"
ARCHITECTURE_SCRIPT = ROOT_DIR / "scripts" / "check-architecture-boundaries.sh"
QUALITY_GATE_SCRIPT = ROOT_DIR / "scripts" / "quality-gate.sh"


def run_guardrail(
    script: Path,
    target: Path,
    *,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if extra_env is not None:
        env.update(extra_env)
    return subprocess.run(
        ["bash", str(script), str(target)],
        cwd=ROOT_DIR,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def write_route(root: Path, source: str) -> None:
    route_dir = root / "src" / "job_runner_platform" / "api" / "routes"
    route_dir.mkdir(parents=True)
    (route_dir / "jobs.py").write_text(source, encoding="utf-8")


def assert_passed(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, result.stdout + result.stderr


def assert_failed(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode != 0, result.stdout + result.stderr


def test_public_safety_guardrail_allows_public_safe_placeholders(
    tmp_path: Path,
) -> None:
    (tmp_path / "README.md").write_text(
        "public-safe portfolio demo\n",
        encoding="utf-8",
    )
    (tmp_path / "example.env").write_text(
        "JOB_RUNNER_AUTH_API_KEYS=\n",
        encoding="utf-8",
    )

    result = run_guardrail(PUBLIC_SAFETY_SCRIPT, tmp_path)

    assert_passed(result)
    assert "Public-safety guardrail passed" in result.stdout


def test_public_safety_guardrail_rejects_accidental_env_files(
    tmp_path: Path,
) -> None:
    (tmp_path / ".env").write_text(
        "JOB_RUNNER_AUTH_API_KEYS=" + ("x" * 40),
        encoding="utf-8",
    )

    result = run_guardrail(PUBLIC_SAFETY_SCRIPT, tmp_path)

    assert_failed(result)
    assert ".env" in result.stdout


def test_public_safety_guardrail_rejects_real_looking_secrets(
    tmp_path: Path,
) -> None:
    access_key = "AKIA" + ("A" * 16)
    (tmp_path / "notes.txt").write_text(
        f"access key for test fixture: {access_key}\n",
        encoding="utf-8",
    )

    result = run_guardrail(PUBLIC_SAFETY_SCRIPT, tmp_path)

    assert_failed(result)
    assert "AWS access key" in result.stdout


def test_public_safety_guardrail_rejects_configured_forbidden_terms(
    tmp_path: Path,
) -> None:
    forbidden_term = "private-system-codename"
    (tmp_path / "notes.md").write_text(
        f"Do not publish {forbidden_term}.\n",
        encoding="utf-8",
    )

    result = run_guardrail(
        PUBLIC_SAFETY_SCRIPT,
        tmp_path,
        extra_env={"JOB_RUNNER_PUBLIC_SAFETY_FORBIDDEN_TERMS": forbidden_term},
    )

    assert_failed(result)
    assert "configured forbidden private term" in result.stdout


def test_architecture_guardrail_allows_thin_service_based_routes(
    tmp_path: Path,
) -> None:
    write_route(
        tmp_path,
        """
from __future__ import annotations

from fastapi import APIRouter

from job_runner_platform.services import JobService

router = APIRouter()


@router.get("/jobs")
async def list_jobs(service: JobService) -> dict[str, str]:
    await service.list_jobs()
    return {"status": "ok"}
""".lstrip(),
    )

    result = run_guardrail(ARCHITECTURE_SCRIPT, tmp_path)

    assert_passed(result)
    assert "Architecture boundary guardrail passed" in result.stdout


def test_architecture_guardrail_rejects_route_database_imports(
    tmp_path: Path,
) -> None:
    write_route(
        tmp_path,
        """
from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from job_runner_platform.database.models import JobModel

router = APIRouter()


@router.get("/jobs")
async def list_jobs(session: object) -> list[object]:
    return [select(JobModel)]
""".lstrip(),
    )

    result = run_guardrail(ARCHITECTURE_SCRIPT, tmp_path)

    assert_failed(result)
    assert "sqlalchemy" in result.stdout
    assert "job_runner_platform.database.models" in result.stdout


def test_architecture_guardrail_rejects_route_redis_imports(
    tmp_path: Path,
) -> None:
    write_route(
        tmp_path,
        """
from __future__ import annotations

from fastapi import APIRouter
from redis.asyncio import Redis

router = APIRouter()


@router.post("/jobs")
async def create_job(redis: Redis) -> dict[str, str]:
    await redis.ping()
    return {"status": "queued"}
""".lstrip(),
    )

    result = run_guardrail(ARCHITECTURE_SCRIPT, tmp_path)

    assert_failed(result)
    assert "redis.asyncio" in result.stdout
    assert "ping" in result.stdout


def test_quality_gate_runs_guardrail_scripts() -> None:
    quality_gate = QUALITY_GATE_SCRIPT.read_text(encoding="utf-8")

    assert "scripts/check-public-safety.sh" in quality_gate
    assert "scripts/check-architecture-boundaries.sh" in quality_gate
