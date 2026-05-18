# BUILD_NOTES.md

## Current state

Tickets 000 through 007 are complete. The repository now has the initial Python 3.12 `src/` package skeleton, uv/hatchling packaging, Ruff, mypy strict mode, pytest, pytest-cov, documentation directories, public-safe example configuration, a reusable quality gate, a FastAPI application shell, explicit job domain/API schemas, PostgreSQL persistence scaffolding with Alembic migrations, an internal repository layer for job persistence/state transitions, a Redis-backed queue abstraction for job-ID dispatch signals, a job service layer for create/get/list/cancel workflows, and FastAPI job routes for those workflows.

Ticket 007 added:

- Thin FastAPI job routes for `POST /jobs`, `GET /jobs`, `GET /jobs/{job_id}`, and `POST /jobs/{job_id}/cancel`.
- API dependency wiring that lazily builds the SQLAlchemy session factory and Redis queue, then constructs `JobService` with `JobRepository` so route handlers do not query the database or call Redis directly.
- Response conversion through the existing Pydantic API schemas, including `from_attributes` support for repository/service job records.
- HTTP behaviour for `201 Created` on new job submission, `200 OK` on idempotency replay, bounded pagination with optional status filtering, clear `404` responses for missing jobs, and `409 Conflict` for terminal-state cancellation conflicts.
- API tests covering creation, idempotency replay, listing with pagination/status filter, fetch by ID, missing job handling, cancellation success/conflict/not-found behaviour, and request validation before service calls.
- README updates documenting the exposed job API surface and current local limitations.

## Quality gates

Latest run:

- `scripts/quality-gate.sh` — passed
  - shell syntax checks
  - `uv sync --locked --all-groups`
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run mypy src tests`
  - `uv run pytest --cov=job_runner_platform --cov-report=term-missing`

Additional validation this cycle:

- `uv run ruff check .` — passed.
- `uv run ruff format --check .` — passed.
- `uv run mypy src tests` — passed.
- `uv run pytest -q` — passed.

## Public-safety notes

This project is an independent public portfolio project.

Do not add employer code, private data, internal URLs, credentials, screenshots, non-public architecture, or anything implying employer endorsement.

Do not implement arbitrary shell command execution. Jobs must be safe allowlisted demo handlers only.

## Latest cycle notes

- Implemented only the API routes required by ticket 007; no job handlers, worker runtime, retry/dead-letter logic, readiness endpoint, metrics, auth, Docker Compose stack, or CI were introduced.
- Preserved the route -> schemas -> services -> repositories -> database/queue boundary. Routes call `JobService` and use Pydantic request/response models; database sessions and Redis queue construction are isolated in API dependency wiring.
- Job routes expose the already-implemented service workflow. A submitted job is persisted and signalled, but no worker exists yet to execute queued jobs.
- No arbitrary command execution, subprocess execution, credentials, private details, or employer-specific content were added.

## Limitations

The API now exposes `/jobs` routes and `/healthz`, but `/readyz`, `/metrics`, worker runtime, job handler execution, auth, Docker Compose, and CI remain future tickets. Local end-to-end job execution still requires future worker and handler tickets. Queue dispatch remains a Redis wake-up signal while PostgreSQL remains the durable source of truth. Concurrent idempotent submissions rely on the database unique index as the final guard; future API transaction handling can add retry-on-conflict behaviour if needed.

## Next recommended ticket

Ticket 008.
