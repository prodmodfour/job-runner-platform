#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT_DIR"

echo "== shell syntax checks =="
for script in scripts/*.sh; do
  [[ -e "$script" ]] || continue
  bash -n "$script"
done

echo "== public-safety guardrail =="
bash scripts/check-public-safety.sh

echo "== architecture boundary guardrail =="
bash scripts/check-architecture-boundaries.sh

echo "== uv sync =="
if [[ -f uv.lock ]]; then
  uv sync --locked --all-groups
else
  uv sync --all-groups
fi

echo "== ruff check =="
uv run ruff check .

echo "== ruff format check =="
uv run ruff format --check .

echo "== mypy =="
uv run mypy src tests

echo "== pytest =="
uv run pytest --cov=job_runner_platform --cov-report=term-missing

echo "== quality gate passed =="
