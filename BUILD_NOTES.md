# BUILD_NOTES.md

## Current state

Tickets 000 through 013 are complete. The repository now has the initial Python
3.12 `src/` package skeleton, uv/hatchling packaging, Ruff, mypy strict mode,
pytest, pytest-cov, documentation directories, public-safe example
configuration, a reusable quality gate, a FastAPI application shell, explicit
job domain/API schemas, PostgreSQL persistence scaffolding with Alembic
migrations, an internal repository layer for job persistence/state transitions,
a Redis-backed queue abstraction for job-ID dispatch signals, a job service
layer for create/get/list/cancel workflows, FastAPI job routes for those
workflows, safe allowlisted built-in demo job handlers, a worker CLI/runtime,
retry/dead-letter behaviour, lease-based stale job recovery, cooperative worker
cancellation handling, and API readiness checks for PostgreSQL and Redis.

Ticket 013 added:

- `GET /readyz` with a response body that reports overall readiness plus
  per-dependency statuses for `postgresql` and `redis`.
- A database-layer readiness probe that executes a minimal SQLAlchemy
  `SELECT 1` query through the configured async session factory.
- A queue readiness probe that uses the existing `JobQueue.is_ready()`
  abstraction, keeping Redis details out of routes.
- A `ReadinessService` that coordinates probes, returns safe public failure
  messages, and keeps route handlers thin.
- Tests for successful readiness responses, `503 Service Unavailable` failure
  responses, safe failure-message handling, the database probe, and the queue
  probe.
- README updates documenting `/readyz` behaviour and the dependency checks.

## Quality gates

Latest run:

- `scripts/quality-gate.sh` — passed
  - shell syntax checks
  - `uv sync --locked --all-groups`
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run mypy src tests`
  - `uv run pytest --cov=job_runner_platform --cov-report=term-missing`

Additional validation this cycle before the full gate:

- `uv run pytest tests/test_readiness.py -q` — passed (`5 passed`).
- `uv run mypy src tests` — passed.
- `uv run ruff check . && uv run ruff format --check .` — passed.
- `uv run pytest -q` — passed (`73 passed`).

## Public-safety notes

This project is an independent public portfolio project.

Do not add employer code, private data, internal URLs, credentials, screenshots,
non-public architecture, or anything implying employer endorsement.

Do not implement arbitrary shell command execution. Jobs must be safe
allowlisted demo handlers only.

## Latest cycle notes

- Implemented only the readiness and dependency checks required by ticket 013;
  Prometheus `/metrics`, optional API key auth, Docker Compose, and CI were not
  introduced.
- Preserved public-safety constraints: readiness executes only a fixed
  `SELECT 1` database probe and a Redis ping through the queue abstraction. It
  does not run shell commands, subprocesses, containers, user-submitted code, or
  host-level operations.
- Kept dependency checks on the intended boundary path: route -> readiness
  service -> database readiness probe / queue abstraction.
- PostgreSQL remains the source of truth for jobs. Redis still carries only job
  UUID dispatch signals; readiness verifies Redis reachability but does not
  inspect or mutate queue contents.

## Limitations

Readiness checks verify connectivity with a minimal PostgreSQL query and Redis
ping; they do not verify that migrations are current or that a worker is
running. Prometheus `/metrics`, optional auth, Docker Compose, and CI remain
future tickets. Local end-to-end execution currently requires separately
managed PostgreSQL and Redis services because the Docker Compose stack is not
implemented yet.

## Next recommended ticket

Ticket 014.
