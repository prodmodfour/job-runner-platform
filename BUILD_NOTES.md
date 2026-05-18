# BUILD_NOTES.md

## Current state

Tickets 000, 001, 002, and 003 are complete. The repository now has the initial Python 3.12 `src/` package skeleton, uv/hatchling packaging, Ruff, mypy strict mode, pytest, pytest-cov, documentation directories, public-safe example configuration, a reusable quality gate, a FastAPI application shell, explicit job domain/API schemas, and PostgreSQL persistence scaffolding with Alembic migrations.

Ticket 001 added:

- FastAPI app factory at `job_runner_platform.api.app:create_app` plus default ASGI app `job_runner_platform.api.app:app`.
- `Settings` loaded from `JOB_RUNNER_`-prefixed environment variables.
- Docs/OpenAPI disabled by default and enabled only with `JOB_RUNNER_DOCS_ENABLED=true`.
- Structured JSON logging with request ID context.
- `X-Request-ID` propagation/generation middleware.
- `GET /healthz` liveness endpoint returning app metadata.
- Tests for health, request IDs, docs configuration, environment-backed settings, and JSON log formatting.
- README configuration/API shell updates and refreshed `example.env` wording.

Ticket 002 added:

- Job domain definitions for safe allowlisted job types, explicit statuses, IDs, attempts, max attempts, priority, JSON payload/result fields, idempotency keys, timestamps, and lease metadata.
- Pydantic schemas for create requests, create responses, detail responses, list responses, and cancellation responses.
- Validation for unsafe job types, JSON-serializable payload/result fields, aware timestamps, bounded attempts/priority, and list count consistency.
- Schema tests covering safe and unsafe job types plus response validation.
- README notes for the current job schema contract.

Ticket 003 added:

- Runtime dependencies for SQLAlchemy asyncio, asyncpg, and Alembic.
- `JOB_RUNNER_DATABASE_URL` settings support with a public-safe local PostgreSQL placeholder default.
- A repository-friendly database package under `src/job_runner_platform/database/` with declarative metadata, a `JobModel`, async engine/sessionmaker helpers, and a transactional session scope helper.
- A PostgreSQL `jobs` table model with UUID primary key, allowlisted job type/status check constraints, JSON payload/result fields, attempts/max attempts, idempotency key, lease fields, timestamps, priority, and useful status/created/idempotency/lease indexes.
- Alembic configuration at `alembic.ini`, async migration environment at `migrations/env.py`, and initial revision `0001_create_jobs_table`.
- Tests for database metadata, PostgreSQL DDL compilation, async engine/session factory setup, and migration file presence.
- README updates for database configuration and Alembic usage.

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

- `uv run alembic upgrade head --sql` — passed without requiring a live database connection.

## Public-safety notes

This project is an independent public portfolio project.

Do not add employer code, private data, internal URLs, credentials, screenshots, non-public architecture, or anything implying employer endorsement.

Do not implement arbitrary shell command execution. Jobs must be safe allowlisted demo handlers only.

## Latest cycle notes

- Added PostgreSQL schema/model and Alembic migration scaffolding only; no repositories, job routes, Redis queueing, worker runtime, or handler execution were introduced in this ticket.
- Kept database access isolated under the database package for future repository use.
- The jobs table stores allowlisted handler names and explicit lifecycle statuses as constrained strings rather than arbitrary commands or executable payloads.
- No arbitrary command execution, subprocess execution, credentials, private details, or employer-specific content were added.

## Limitations

The API shell still exposes only `/healthz`; `/readyz`, `/metrics`, job routes, repository methods, Redis queueing, worker runtime, auth, Docker Compose, and CI remain future tickets. A local PostgreSQL service is not yet provided by the repository, so applying migrations requires an externally available local PostgreSQL instance until Docker Compose is added.

## Next recommended ticket

Ticket 004.
