# BUILD_NOTES.md

## Current state

Tickets 000 and 001 are complete. The repository now has the initial Python 3.12 `src/` package skeleton, uv/hatchling packaging, Ruff, mypy strict mode, pytest, pytest-cov, documentation directories, public-safe example configuration, a reusable quality gate, and a FastAPI application shell.

Ticket 001 added:

- FastAPI app factory at `job_runner_platform.api.app:create_app` plus default ASGI app `job_runner_platform.api.app:app`.
- `Settings` loaded from `JOB_RUNNER_`-prefixed environment variables.
- Docs/OpenAPI disabled by default and enabled only with `JOB_RUNNER_DOCS_ENABLED=true`.
- Structured JSON logging with request ID context.
- `X-Request-ID` propagation/generation middleware.
- `GET /healthz` liveness endpoint returning app metadata.
- Tests for health, request IDs, docs configuration, environment-backed settings, and JSON log formatting.
- README configuration/API shell updates and refreshed `example.env` wording.

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

- Added FastAPI dependencies and test client support.
- Kept routes thin: `/healthz` performs only process liveness metadata reporting and does not call databases or Redis.
- Request ID propagation is implemented independently of future business/job routes.
- No arbitrary command execution, subprocess execution, credentials, or private details were added.

## Limitations

The API shell has only `/healthz`; `/readyz`, `/metrics`, job schemas, persistence, Redis queueing, worker runtime, auth, Docker Compose, and CI remain future tickets.

## Next recommended ticket

Ticket 002.
