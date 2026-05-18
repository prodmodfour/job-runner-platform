# BUILD_NOTES.md

## Current state

Tickets 000 through 019 are complete. The repository now has the initial Python
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
configuration, GitHub Actions CI, and automation guardrail scripts.

Ticket 019 added:

- `scripts/check-public-safety.sh`, which scans repository text files for
  obvious public-safety risks including accidental `.env` files, real-looking
  secrets, internal/private hostnames, and locally configured forbidden private
  terms.
- `scripts/check-architecture-boundaries.sh`, which parses FastAPI route files
  and fails on obvious direct imports/calls into database, repository, queue,
  SQLAlchemy, or Redis layers.
- Quality gate and GitHub Actions wiring so both guardrails run as required
  checks.
- Tests in `tests/test_guardrail_scripts.py` covering passing cases and
  representative public-safety and layering failures.
- README and `.gitignore` updates documenting ignored local forbidden-term
  guardrail files and the expanded quality gate.

## Quality gates

Latest run:

- `scripts/quality-gate.sh` — passed
  - shell syntax checks
  - `scripts/check-public-safety.sh`
  - `scripts/check-architecture-boundaries.sh`
  - `uv sync --locked --all-groups`
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run mypy src tests`
  - `uv run pytest --cov=job_runner_platform --cov-report=term-missing`
    (`101 passed`)

Additional validation this cycle:

- `bash -n scripts/*.sh` — passed.
- `scripts/check-public-safety.sh` — passed.
- `scripts/check-architecture-boundaries.sh` — passed.
- `uv run pytest tests/test_guardrail_scripts.py tests/test_ci_workflow.py -q`
  — passed (`11 passed`).
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src tests`
  — passed.

## Public-safety notes

This project is an independent public portfolio project.

Do not add employer code, private data, internal URLs, credentials, screenshots,
non-public architecture, or anything implying employer endorsement.

Do not implement arbitrary shell command execution. Jobs must be safe
allowlisted demo handlers only.

The Compose stack and CI PostgreSQL service use local placeholder values only.
They are development/demo settings, not a production security baseline. The new
public-safety guardrail intentionally supports private forbidden-term lists via
ignored local files or an environment variable; do not commit those private
terms.

## Latest cycle notes

- Implemented only the automation guardrail scope required by ticket 019;
  broader architecture and operations docs, ADR completion, smoke/demo scripts,
  and final README polish remain future tickets.
- Preserved runtime architecture and job execution behaviour: no route,
  service, repository, queue, worker, or handler implementation code changed for
  this automation-only ticket.
- Preserved public-safety constraints: no employer/private details, external
  secrets, arbitrary user-submitted commands, subprocess job handlers, or host
  filesystem mutation features were added.
- CI now runs concrete guardrail scripts rather than optional placeholders.

## Limitations

The guardrails are intentionally lightweight static checks. They catch obvious
public-safety and route-layering mistakes, but they are not a substitute for
human review, secret scanning services, or full static analysis. The public
forbidden-term check requires terms to be supplied locally through ignored files
or `JOB_RUNNER_PUBLIC_SAFETY_FORBIDDEN_TERMS`; the repository does not commit
private employer-specific terms.

The Docker Compose stack is for local development and portfolio demos only. It
uses placeholder local credentials and should not be treated as a production
security baseline. The API container runs Alembic migrations automatically for
local convenience; production deployments would usually run migrations as an
explicit release step. The Grafana dashboard is intentionally basic and is not a
production alerting baseline. Metrics remain process-local; the current Compose
configuration scrapes one API container and one worker container separately, and
a multi-process or multi-worker deployment would need deployment-specific
labels, aggregation, and alerting. Broader documentation and smoke demo scripts
remain future tickets. Readiness checks verify PostgreSQL and Redis connectivity
only; they do not verify that a worker is running.

## Next recommended ticket

Ticket 020.
