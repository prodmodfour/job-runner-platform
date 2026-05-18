# BUILD_NOTES.md

## Current state

Tickets 000, 001, and 002 are complete. The repository now has the initial Python 3.12 `src/` package skeleton, uv/hatchling packaging, Ruff, mypy strict mode, pytest, pytest-cov, documentation directories, public-safe example configuration, a reusable quality gate, a FastAPI application shell, and explicit job domain/API schemas.

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

- Added domain/schema-only job modeling; no persistence, Redis, worker runtime, or job routes were introduced in this ticket.
- Restricted job type validation to the safe built-in demo handler names: `echo`, `sleep`, `checksum`, `fail_once`, and `always_fail`.
- Kept route boundaries unchanged; existing routes remain thin and do not call databases or Redis.
- No arbitrary command execution, subprocess execution, credentials, or private details were added.

## Limitations

The API shell still exposes only `/healthz`; `/readyz`, `/metrics`, job routes, PostgreSQL persistence, Redis queueing, worker runtime, auth, Docker Compose, and CI remain future tickets.

## Next recommended ticket

Ticket 003.
