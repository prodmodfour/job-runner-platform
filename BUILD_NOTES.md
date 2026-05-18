# BUILD_NOTES.md

## Current state

Tickets 000 through 006 are complete. The repository now has the initial Python 3.12 `src/` package skeleton, uv/hatchling packaging, Ruff, mypy strict mode, pytest, pytest-cov, documentation directories, public-safe example configuration, a reusable quality gate, a FastAPI application shell, explicit job domain/API schemas, PostgreSQL persistence scaffolding with Alembic migrations, an internal repository layer for job persistence/state transitions, a Redis-backed queue abstraction for job-ID dispatch signals, and a job service layer for create/get/list/cancel workflows.

Ticket 006 added:

- `job_runner_platform.services.JobService`, which coordinates repository operations with queue dispatch signals while keeping routes and workers free of database/Redis details.
- Service-layer result objects for job creation, paginated listing, and cancellation outcomes.
- Service-layer errors for invalid job types/statuses, invalid pagination, missing jobs, and terminal-state cancellation conflicts so future API routes can map them to clear HTTP responses.
- Safe allowlist validation before persistence, idempotency-key replay that returns the existing job without enqueueing another signal, bounded list pagination, and cancellation behaviour for queued/running jobs.
- Tests covering job creation/get, idempotency replay, invalid job type rejection, pagination/status filtering, queued cancellation, running cancellation requests, and terminal cancellation conflicts.
- README updates describing the service layer and current non-exposed API status.

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

- Implemented only the service layer required by ticket 006; no job API routes, worker runtime, handler execution, readiness endpoint, metrics, Docker Compose stack, or CI were introduced.
- Kept SQL in repositories and Redis calls behind the queue abstraction. The service depends on narrow repository/queue interfaces and contains the business workflow for creation, idempotency, listing, and cancellation.
- Queued jobs are cancelled immediately by the service/repository path. Running jobs become `cancel_requested`; worker-side cooperative cancellation remains a future ticket.
- No arbitrary command execution, subprocess execution, credentials, private details, or employer-specific content were added.

## Limitations

The API shell still exposes only `/healthz`; job routes, `/readyz`, `/metrics`, worker runtime, auth, Docker Compose, and CI remain future tickets. The service layer is testable and ready for future routes, but it is not yet wired into FastAPI endpoints. Queue dispatch is still only a signal: an existing queued row remains the durable source of truth if a Redis signal is duplicated or lost. Concurrent idempotent submissions rely on the database unique index as the final guard; future API transaction handling can add retry-on-conflict behaviour if needed.

## Next recommended ticket

Ticket 007.
