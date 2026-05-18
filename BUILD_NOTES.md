# BUILD_NOTES.md

## Current state

Tickets 000 through 018 are complete. The repository now has the initial Python
3.12 `src/` package skeleton, uv/hatchling packaging, Ruff, mypy strict mode,
pytest, pytest-cov, documentation directories, public-safe example
configuration, a reusable quality gate, a FastAPI application shell, explicit
job domain/API schemas, PostgreSQL persistence scaffolding with Alembic
migrations, an internal repository layer for job persistence/state transitions,
a Redis-backed queue abstraction for job-ID dispatch signals, a job service
layer for create/get/list/cancel workflows, FastAPI job routes for those
workflows, safe allowlisted built-in demo job handlers, a worker CLI/runtime,
retry/dead-letter behaviour, lease-based stale job recovery, cooperative worker
cancellation handling, API readiness checks for PostgreSQL and Redis,
Prometheus metrics exposition, optional API key authentication for business job
endpoints, a local Docker Compose stack, local Prometheus/Grafana observability
configuration, and GitHub Actions CI.

Ticket 018 added:

- `.github/workflows/ci.yml` with a Python 3.12 GitHub Actions quality job.
- A PostgreSQL 16 service container for Alembic migration validation.
- CI steps for shell syntax checks, optional public-safety guardrail scripts
  when present, optional architecture/layering guardrail scripts when present,
  `uv sync --locked --all-groups`, Ruff linting, Ruff format checks, mypy,
  `docker compose config`, `alembic upgrade head`, and pytest with coverage.
- Tests in `tests/test_ci_workflow.py` that assert the workflow includes the
  required CI coverage and PostgreSQL service configuration.
- README updates documenting the new CI workflow and how it extends the local
  quality gate.

## Quality gates

Latest run:

- `scripts/quality-gate.sh` — passed
  - shell syntax checks
  - `uv sync --locked --all-groups`
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run mypy src tests`
  - `uv run pytest --cov=job_runner_platform --cov-report=term-missing`
    (`93 passed`)

Additional validation this cycle:

- `uv run pytest tests/test_ci_workflow.py -q` — passed (`3 passed`).
- `docker compose config` — passed.

## Public-safety notes

This project is an independent public portfolio project.

Do not add employer code, private data, internal URLs, credentials, screenshots,
non-public architecture, or anything implying employer endorsement.

Do not implement arbitrary shell command execution. Jobs must be safe
allowlisted demo handlers only.

The Compose stack and CI PostgreSQL service use local placeholder values only.
They are development/demo settings, not a production security baseline.

## Latest cycle notes

- Implemented only the GitHub Actions CI scope required by ticket 018;
  automation guardrail scripts, broader architecture and operations docs, ADR
  completion, smoke/demo scripts, and final README polish remain future tickets.
- Preserved architecture boundaries: no route, service, repository, queue,
  worker, or handler implementation code changed for this CI-only ticket.
- Preserved public-safety constraints: no employer/private details, external
  secrets, arbitrary user-submitted commands, subprocess job handlers, or host
  filesystem mutation features were added.
- The CI workflow conditionally runs guardrail scripts if they exist, so ticket
  019 can add the concrete public-safety and architecture checks without
  changing the CI contract substantially.

## Limitations

The Docker Compose stack is for local development and portfolio demos only. It
uses placeholder local credentials and should not be treated as a production
security baseline. The API container runs Alembic migrations automatically for
local convenience; production deployments would usually run migrations as an
explicit release step. The Grafana dashboard is intentionally basic and is not a
production alerting baseline. Metrics remain process-local; the current Compose
configuration scrapes one API container and one worker container separately, and
a multi-process or multi-worker deployment would need deployment-specific
labels, aggregation, and alerting. Guardrail scripts are still placeholders in
CI until ticket 019 adds them. Broader documentation and smoke demo scripts
remain future tickets. Readiness checks verify PostgreSQL and Redis connectivity
only; they do not verify that a worker is running.

## Next recommended ticket

Ticket 019.
