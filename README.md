# Job Runner Platform

`job-runner-platform` is an independent public portfolio project that demonstrates backend and platform engineering through a production-style background job platform.

The repository is intentionally public-safe: it uses only generic local configuration, fake demo data, and documented constraints. It is not affiliated with any employer or private system.

## Current status

The repository now includes the initial Python package skeleton, a FastAPI application shell with structured JSON logging, `X-Request-ID` propagation, documentation disabled by default, `GET /healthz`, explicit job domain/API schemas, the initial PostgreSQL jobs table model plus Alembic migration, and an internal SQLAlchemy repository layer for job persistence/state transitions. Redis dispatch, service/API job routes, worker runtime, retries, cancellation handling in workers, leases recovery loops, metrics, Docker Compose, and CI will be added in later tickets.

## Public-safety constraints

This project must not include employer code, private data, internal URLs or hostnames, credentials, tokens, screenshots of private systems, non-public architecture, or anything implying employer endorsement.

The platform must not implement arbitrary shell command execution. Future jobs are limited to safe allowlisted demo handlers such as `echo`, `sleep`, `checksum`, `fail_once`, and `always_fail`.

## Backend/platform skills demonstrated

The completed project is intended to demonstrate:

- FastAPI backend API design
- PostgreSQL persistence and migrations
- Redis-backed queue/dispatch signalling
- Worker process design
- retries, dead-letter handling, idempotency, cancellation, and leases
- structured JSON logging and request ID propagation
- Prometheus metrics and health/readiness checks
- Docker Compose local operations
- GitHub Actions CI, tests, docs, runbooks, and architecture decisions

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Make (optional convenience wrapper)

## Development quick start

```bash
uv sync --all-groups
uv run pytest
scripts/quality-gate.sh
```

Or use Make:

```bash
make quality
```

## Repository layout

```text
src/job_runner_platform/   Python package source
tests/                     pytest test suite
docs/                      project documentation
docs/decisions/            architecture decision records
scripts/                   local automation and quality gates
```

## Configuration

Runtime configuration uses environment variables prefixed with `JOB_RUNNER_`. See `example.env` for public-safe local placeholders.

Implemented app-shell settings:

| Environment variable | Default | Purpose |
| --- | --- | --- |
| `JOB_RUNNER_APP_NAME` | `job-runner-platform` | FastAPI application title and health metadata. |
| `JOB_RUNNER_APP_VERSION` | `0.1.0` | FastAPI/OpenAPI version and health metadata. |
| `JOB_RUNNER_ENVIRONMENT` | `local` | Environment label emitted by health responses and logs. |
| `JOB_RUNNER_LOG_LEVEL` | `INFO` | Root structured logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`). |
| `JOB_RUNNER_DOCS_ENABLED` | `false` | Enables `/docs`, `/redoc`, and `/openapi.json` only when explicitly set to `true`. |
| `JOB_RUNNER_DATABASE_URL` | `postgresql+asyncpg://localhost:5432/job_runner` | Async SQLAlchemy database URL used by Alembic and future repositories. |

The ASGI application factory is `job_runner_platform.api.app:create_app`, and the default app object is `job_runner_platform.api.app:app`.

## Job domain model

The job schema layer defines the future API contract for safe demo jobs. Supported job types are allowlisted values only: `echo`, `sleep`, `checksum`, `fail_once`, and `always_fail`. Job statuses are explicit: `queued`, `running`, `succeeded`, `failed`, `cancel_requested`, `cancelled`, and `dead_lettered`.

Job request/response schemas cover creation, detail views, list pages, cancellation responses, idempotency keys, attempts/max attempts, JSON payload/result fields, errors, timestamps, and lease metadata. The PostgreSQL `jobs` table mirrors those fields, with indexes for status, creation time, idempotency keys, and lease expiry. An internal repository layer now owns SQLAlchemy access for creation, fetching/listing, idempotency lookup, cancellation requests, worker claim/complete/fail/dead-letter/requeue transitions, and stale lease lookup. Job routes are not exposed until a later ticket adds services and queueing.

## Database migrations

Alembic is configured at `alembic.ini` with migration scripts in `migrations/`. The initial revision creates the PostgreSQL source-of-truth `jobs` table.

```bash
JOB_RUNNER_DATABASE_URL=postgresql+asyncpg://localhost:5432/job_runner uv run alembic upgrade head
```

A local PostgreSQL service is not yet provided by this repository; Docker Compose arrives in a later ticket.

## Current API shell

- `GET /healthz` returns liveness metadata for the API process.
- All HTTP responses include `X-Request-ID`; an incoming value is propagated and a UUID is generated when the header is absent.
- Swagger/ReDoc/OpenAPI routes are disabled by default for safer public-facing defaults.

## Quality gate

`scripts/quality-gate.sh` currently runs:

- shell syntax checks for repository scripts
- `uv sync`
- Ruff lint checks
- Ruff format checks
- mypy in strict mode
- pytest with coverage
