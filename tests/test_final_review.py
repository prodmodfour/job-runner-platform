from __future__ import annotations

import re
from pathlib import Path

from job_runner_platform.domain.jobs import JobType
from job_runner_platform.handlers import BUILTIN_JOB_HANDLERS
from job_runner_platform.settings import Settings

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_RUNTIME_SNIPPETS = (
    "import subprocess",
    "from subprocess",
    "subprocess.",
    "os.system(",
    "os.popen(",
    "eval(",
    "exec(",
    "shell=True",
)
EXPECTED_HANDLER_NAMES = ("echo", "sleep", "checksum", "fail_once", "always_fail")


def _settings_environment_variables() -> set[str]:
    return {f"JOB_RUNNER_{field_name.upper()}" for field_name in Settings.model_fields}


def _parse_example_env_keys(path: Path) -> set[str]:
    keys: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, separator, _value = stripped.partition("=")
        assert separator == "=", f"example env line is not KEY=value: {line!r}"
        keys.add(key)
    return keys


def _compose_job_runner_keys() -> set[str]:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    return set(re.findall(r"\b(JOB_RUNNER_[A-Z0-9_]+)\s*:", compose))


def test_final_automation_status_and_ticket_statuses_are_done() -> None:
    tickets = (ROOT / "BUILD_TICKETS.md").read_text(encoding="utf-8")

    assert "AUTOMATION_STATUS: DONE" in tickets
    ticket_statuses = re.findall(r"^Status: ([A-Z_]+)$", tickets, flags=re.MULTILINE)
    assert ticket_statuses
    assert set(ticket_statuses) == {"DONE"}


def test_runtime_source_does_not_use_arbitrary_execution_apis() -> None:
    for path in (ROOT / "src" / "job_runner_platform").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        for snippet in FORBIDDEN_RUNTIME_SNIPPETS:
            assert snippet not in source, (
                f"{path.relative_to(ROOT)} contains {snippet!r}"
            )


def test_builtin_handler_registry_remains_exactly_allowlisted() -> None:
    registered_names = tuple(job_type.value for job_type in BUILTIN_JOB_HANDLERS)

    assert registered_names == EXPECTED_HANDLER_NAMES
    assert set(BUILTIN_JOB_HANDLERS) == set(JobType)


def test_public_example_and_compose_only_use_implemented_settings() -> None:
    settings_keys = _settings_environment_variables()

    assert _parse_example_env_keys(ROOT / "example.env") == settings_keys
    assert _compose_job_runner_keys() <= settings_keys
