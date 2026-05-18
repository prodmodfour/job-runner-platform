#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
TARGET_ROOT=${1:-$ROOT_DIR}

python3 - "$TARGET_ROOT" <<'PY'
from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()

SKIP_DIR_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "htmlcov",
    "venv",
}
SKIP_FILE_SUFFIXES = {
    ".db",
    ".gif",
    ".ico",
    ".jpg",
    ".jpeg",
    ".lock",
    ".pdf",
    ".png",
    ".pyc",
    ".sqlite",
    ".webp",
}
PUBLIC_ENV_FILE_NAMES = {".env.example", "example.env"}
FORBIDDEN_TERM_CONFIG_FILES = {
    ".public-safety-denylist",
    ".public-safety-forbidden-terms",
}
MAX_TEXT_FILE_BYTES = 1_000_000

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private key block", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")),
    ("AWS access key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{36,}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    ("Stripe live secret key", re.compile(r"\bsk_live_[A-Za-z0-9]{24,}\b")),
)
SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(?:password|passwd|secret|token|api[_-]?key|private[_-]?key)\b"
    r"\s*[:=]\s*['\"]?([^'\"\s#]{32,})",
)
INTERNAL_HOSTNAME_PATTERN = re.compile(
    r"(?i)\b(?:https?://|postgres(?:ql)?(?:\+[a-z0-9_]+)?://|redis://|amqp://)?"
    r"[a-z0-9][a-z0-9-]*(?:\.[a-z0-9][a-z0-9-]*)*"
    r"\.(?:corp|internal|intranet|lan|private)(?::\d{1,5})?(?:[/\s]|$)",
)


@dataclass(frozen=True, slots=True)
class Finding:
    path: Path
    line: int
    message: str


def main() -> int:
    if not ROOT.exists() or not ROOT.is_dir():
        print(f"public-safety guardrail root does not exist: {ROOT}", file=sys.stderr)
        return 2

    findings: list[Finding] = []
    findings.extend(find_accidental_env_files(ROOT))

    forbidden_terms = load_forbidden_terms(ROOT)
    for path in iter_candidate_files(ROOT):
        if should_skip_path(path):
            continue
        text = read_text(path)
        if text is None:
            continue
        relative_path = path.relative_to(ROOT)
        findings.extend(scan_text(relative_path, text, forbidden_terms))

    if findings:
        print("Public-safety guardrail failed. Review these findings:")
        for finding in findings:
            print(f"- {finding.path}:{finding.line}: {finding.message}")
        print(
            "Resolve the finding or, for a false positive, narrow the committed "
            "example to public-safe placeholder data."
        )
        return 1

    print("Public-safety guardrail passed.")
    return 0


def find_accidental_env_files(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in root.rglob(".env*"):
        if not path.is_file() or should_skip_path(path):
            continue
        if path.name in PUBLIC_ENV_FILE_NAMES:
            continue
        findings.append(
            Finding(
                path=path.relative_to(root),
                line=1,
                message="do not commit or keep local .env secret files in the repo tree",
            )
        )
    return findings


def load_forbidden_terms(root: Path) -> tuple[str, ...]:
    raw_terms: list[str] = []
    env_value = os.environ.get("JOB_RUNNER_PUBLIC_SAFETY_FORBIDDEN_TERMS", "")
    raw_terms.extend(split_terms(env_value))

    for filename in FORBIDDEN_TERM_CONFIG_FILES:
        path = root / filename
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                raw_terms.append(stripped)

    unique_terms = sorted({term.casefold() for term in raw_terms if len(term) >= 3})
    return tuple(unique_terms)


def split_terms(value: str) -> list[str]:
    terms: list[str] = []
    for chunk in re.split(r"[,\n]", value):
        stripped = chunk.strip()
        if stripped:
            terms.append(stripped)
    return terms


def iter_candidate_files(root: Path) -> list[Path]:
    git_files = git_tracked_and_untracked_files(root)
    if git_files is not None:
        return git_files
    return walk_files(root)


def git_tracked_and_untracked_files(root: Path) -> list[Path] | None:
    try:
        completed = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return None

    paths: list[Path] = []
    for raw_path in completed.stdout.split(b"\0"):
        if not raw_path:
            continue
        try:
            relative = Path(raw_path.decode("utf-8"))
        except UnicodeDecodeError:
            continue
        path = root / relative
        if path.is_file():
            paths.append(path)
    return paths


def walk_files(root: Path) -> list[Path]:
    paths: list[Path] = []
    for directory, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIR_NAMES]
        directory_path = Path(directory)
        for filename in filenames:
            path = directory_path / filename
            if path.is_file():
                paths.append(path)
    return paths


def should_skip_path(path: Path) -> bool:
    parts = set(path.parts)
    if parts.intersection(SKIP_DIR_NAMES):
        return True
    if path.name in FORBIDDEN_TERM_CONFIG_FILES:
        return True
    return path.suffix.lower() in SKIP_FILE_SUFFIXES


def read_text(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if len(data) > MAX_TEXT_FILE_BYTES or b"\0" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def scan_text(
    relative_path: Path,
    text: str,
    forbidden_terms: tuple[str, ...],
) -> list[Finding]:
    findings: list[Finding] = []
    lines = text.splitlines()

    for line_number, line in enumerate(lines, start=1):
        findings.extend(scan_line(relative_path, line_number, line, forbidden_terms))
    return findings


def scan_line(
    relative_path: Path,
    line_number: int,
    line: str,
    forbidden_terms: tuple[str, ...],
) -> list[Finding]:
    findings: list[Finding] = []
    for label, pattern in SECRET_PATTERNS:
        if pattern.search(line):
            findings.append(Finding(relative_path, line_number, f"possible {label}"))

    if SECRET_ASSIGNMENT_PATTERN.search(line):
        findings.append(
            Finding(relative_path, line_number, "possible long secret assignment")
        )

    if INTERNAL_HOSTNAME_PATTERN.search(line):
        findings.append(
            Finding(relative_path, line_number, "possible internal/private hostname")
        )

    folded_line = line.casefold()
    for term in forbidden_terms:
        if term in folded_line:
            findings.append(
                Finding(
                    relative_path,
                    line_number,
                    "configured forbidden private term is present",
                )
            )
    return findings


if __name__ == "__main__":
    raise SystemExit(main())
PY
