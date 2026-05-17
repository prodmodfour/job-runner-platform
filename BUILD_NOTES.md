# BUILD_NOTES.md

## Current state

Ticket 000 is complete. The repository now has the initial Python 3.12 `src/` package skeleton, uv/hatchling packaging, Ruff, mypy strict mode, pytest, pytest-cov, documentation directories, public-safe example configuration, and a reusable quality gate.

## Quality gates

Latest run:

- `scripts/quality-gate.sh` — passed
  - shell syntax checks
  - `uv sync --locked --all-groups`
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run mypy src tests`
  - `uv run pytest --cov=job_runner_platform --cov-report=term-missing`

## Public-safety notes

This project is an independent public portfolio project.

Do not add employer code, private data, internal URLs, credentials, screenshots, non-public architecture, or anything implying employer endorsement.

Do not implement arbitrary shell command execution. Jobs must be safe allowlisted demo handlers only.

## Latest cycle notes

- Added `README.md` with portfolio framing, public-safety constraints, no arbitrary command execution rule, skills demonstrated, quick start, layout, configuration, and quality gate notes.
- Added `pyproject.toml`, generated `uv.lock`, and created the package under `src/job_runner_platform/`.
- Added a basic import test in `tests/test_import.py`.
- Added `docs/` and `docs/decisions/` placeholders for later tickets.
- Replaced the quality gate with an executable shell script and added Makefile convenience targets.

## Limitations

Only the bootstrap skeleton exists. The FastAPI application, settings, logging, database, queue, worker, metrics, Docker Compose, CI, and detailed operations docs remain future tickets.

## Next recommended ticket

Ticket 001.
