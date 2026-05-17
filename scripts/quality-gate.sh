
---

## `scripts/quality-gate.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "== shell syntax checks =="
bash -n scripts/quality-gate.sh

if [[ -f scripts/build-loop.sh ]]; then
  bash -n scripts/build-loop.sh
fi

if [[ -f pyproject.toml ]]; then
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

  if [[ -d src ]]; then
    echo "== mypy =="
    uv run mypy src tests
  fi

  if [[ -d tests ]]; then
    echo "== pytest =="
    uv run pytest --cov=src --cov-report=term-missing
  fi
fi

if [[ -f docker-compose.yml ]]; then
  echo "== docker compose config =="
  docker compose config >/dev/null
fi

if [[ -f scripts/check-no-private-terms.py ]]; then
  echo "== public-safety guardrail =="
  uv run python scripts/check-no-private-terms.py
fi

if [[ -f scripts/check-layering.py ]]; then
  echo "== layering guardrail =="
  uv run python scripts/check-layering.py
fi

echo "== quality gate passed =="
