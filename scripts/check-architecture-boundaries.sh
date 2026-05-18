#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
TARGET_ROOT=${1:-$ROOT_DIR}

python3 - "$TARGET_ROOT" <<'PY'
from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
ROUTES_DIR = ROOT / "src" / "job_runner_platform" / "api" / "routes"

PROHIBITED_IMPORT_PREFIXES = (
    "asyncpg",
    "redis",
    "sqlalchemy",
    "job_runner_platform.database",
    "job_runner_platform.queues",
    "job_runner_platform.repositories",
)
PROHIBITED_CALL_NAMES = {
    "delete",
    "insert",
    "select",
    "text",
    "update",
}
PROHIBITED_CALL_ATTRIBUTES = {
    "blpop",
    "brpop",
    "commit",
    "execute",
    "flush",
    "from_url",
    "hget",
    "hset",
    "lpop",
    "lpush",
    "ping",
    "publish",
    "rpop",
    "rpush",
    "rollback",
    "scalar",
    "scalars",
}


@dataclass(frozen=True, slots=True)
class Finding:
    path: Path
    line: int
    message: str


def main() -> int:
    if not ROOT.exists() or not ROOT.is_dir():
        print(f"architecture guardrail root does not exist: {ROOT}", file=sys.stderr)
        return 2
    if not ROUTES_DIR.is_dir():
        print(f"route directory does not exist: {ROUTES_DIR}", file=sys.stderr)
        return 2

    findings: list[Finding] = []
    for route_file in sorted(ROUTES_DIR.rglob("*.py")):
        if route_file.name == "__init__.py":
            continue
        findings.extend(scan_route_file(route_file))

    if findings:
        print("Architecture boundary guardrail failed. Review these findings:")
        for finding in findings:
            print(f"- {finding.path}:{finding.line}: {finding.message}")
        print(
            "Routes should stay thin and use services; direct database, repository, "
            "queue, SQLAlchemy, or Redis access belongs in lower layers."
        )
        return 1

    print("Architecture boundary guardrail passed.")
    return 0


def scan_route_file(path: Path) -> list[Finding]:
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [
            Finding(path.relative_to(ROOT), 1, f"could not read route file: {exc}")
        ]

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return [
            Finding(
                path.relative_to(ROOT),
                exc.lineno or 1,
                f"could not parse route file: {exc.msg}",
            )
        ]

    relative_path = path.relative_to(ROOT)
    findings: list[Finding] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            findings.extend(scan_import(relative_path, node))
        elif isinstance(node, ast.ImportFrom):
            findings.extend(scan_import_from(relative_path, node))
        elif isinstance(node, ast.Call):
            finding = scan_call(relative_path, node)
            if finding is not None:
                findings.append(finding)
    return findings


def scan_import(relative_path: Path, node: ast.Import) -> list[Finding]:
    findings: list[Finding] = []
    for alias in node.names:
        if is_prohibited_module(alias.name):
            findings.append(
                Finding(
                    relative_path,
                    node.lineno,
                    f"route imports lower-layer module '{alias.name}' directly",
                )
            )
    return findings


def scan_import_from(relative_path: Path, node: ast.ImportFrom) -> list[Finding]:
    module = node.module or ""
    if is_prohibited_module(module):
        return [
            Finding(
                relative_path,
                node.lineno,
                f"route imports lower-layer module '{module}' directly",
            )
        ]
    return []


def scan_call(relative_path: Path, node: ast.Call) -> Finding | None:
    func = node.func
    if isinstance(func, ast.Name) and func.id in PROHIBITED_CALL_NAMES:
        return Finding(
            relative_path,
            node.lineno,
            f"route calls likely database helper '{func.id}' directly",
        )
    if isinstance(func, ast.Attribute) and func.attr in PROHIBITED_CALL_ATTRIBUTES:
        return Finding(
            relative_path,
            node.lineno,
            f"route calls likely database/Redis method '{func.attr}' directly",
        )
    return None


def is_prohibited_module(module: str) -> bool:
    return any(
        module == prefix or module.startswith(f"{prefix}.")
        for prefix in PROHIBITED_IMPORT_PREFIXES
    )


if __name__ == "__main__":
    raise SystemExit(main())
PY
