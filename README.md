![CI](https://github.com/prodmodfour/job-runner-platform/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-backend-green)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-source%20of%20truth-blue)
![Redis](https://img.shields.io/badge/Redis-dispatch%20signal-red)
# Job Runner Platform

**A production-style FastAPI, PostgreSQL, Redis, and worker-based background job platform built as a public-safe backend/platform engineering portfolio project.**

This repository is designed for reviewers who want to see practical backend and platform work in one place: API design, durable persistence, Redis dispatch signalling, worker lifecycle management, retries, dead-letter handling, idempotency, cooperative cancellation, leases, structured logs, Prometheus metrics, Docker Compose, CI, guardrails, tests, runbooks, and architecture decisions.

Public-safe by design: the project is independent and uses only local placeholder configuration plus fake demo data. **No arbitrary shell command execution.** Jobs can run only the built-in allowlisted demo handlers: `echo`, `sleep`, `checksum`, `fail_once`, and `always_fail`.

## Portfolio framing

`job-runner-platform` demonstrates how I structure a service that has to coordinate API requests, durable state, transient dispatch signals, and background workers without letting framework or infrastructure concerns leak across layers.

What to look for during review:

- Thin FastAPI routes with validation in schemas and workflow in services.
- PostgreSQL as the source of truth, managed through SQLAlchemy asyncio and Alembic.
- Redis used only as a job-ID dispatch signal, not as the durable job store.
- A worker runtime that claims jobs with leases, handles duplicate queue messages safely, retries failures, dead-letters exhausted jobs, and cooperatively observes cancellation.
- Structured JSON logging, `X-Request-ID` propagation, health/readiness probes, and Prometheus metrics.
- Local Docker Compose operations, GitHub Actions CI, quality gates, guardrails, docs, runbooks, and ADRs.

## Implemented scope

- **API:** `GET /healthz`, `GET /readyz`, `GET /metrics`, `POST /jobs`, `GET /jobs`, `GET /jobs/{job_id}`, and `POST /jobs/{job_id}/cancel`.
- **Job model:** explicit statuses (`queued`, `running`, `succeeded`, `failed`, `cancel_requested`, `cancelled`, `dead_lettered`), attempts, max attempts, priority, payload/result JSON, errors, idempotency keys, timestamps, and lease metadata.
- **Persistence:** async SQLAlchemy session setup, PostgreSQL `jobs` table, Alembic migration, indexes, repository-owned SQL, and integration-style repository tests.
- **Queue dispatch:** Redis-backed queue abstraction plus in-memory fake for tests; PostgreSQL remains authoritative and duplicate Redis signals are safe.
- **Worker:** CLI/runtime with worker IDs, stale lease recovery, safe handler execution, retry/dead-letter behaviour, cooperative cancellation, and graceful stop between jobs.
- **Observability:** structured JSON logs, request IDs, readiness checks, Prometheus counters/histograms, local Prometheus scrape config, Grafana provisioning, and a basic dashboard.
- **Operations and automation:** Dockerfile, Docker Compose stack, smoke demo script, GitHub Actions CI, public-safety guardrail, architecture-boundary guardrail, Ruff, mypy strict mode, pytest, and coverage.

## Public-safety constraints

This is an independent public portfolio project. It must not include employer code, private data, internal URLs or hostnames, credentials, tokens, screenshots of private systems, non-public architecture, or anything implying employer endorsement.

The platform must not run arbitrary user-submitted commands, scripts, Docker containers, Python code strings, subprocesses, or host-level operations. Job execution is intentionally limited to safe built-in demo handlers.

## Out of scope

The project intentionally does not implement:

- arbitrary command execution, user-provided code execution, or user-supplied container execution
- production multi-tenant authorization/RBAC
- production secret management, TLS termination, network policy, backups, or alerting
- autoscaling or high-availability deployment manifests
- long-running unbounded handlers or worker lease heartbeats
- a full admin UI

Those choices keep the repository safe for public review while still demonstrating backend/platform engineering fundamentals.

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Docker with Docker Compose v2 for the local stack
- Make, optional, for convenience targets

## Quick start

Run the full local demo stack:

```bash
docker compose up --build
```

The stack builds one application image and starts API, worker, PostgreSQL, Redis, Prometheus, and Grafana services. The API service runs Alembic migrations before starting Uvicorn.

Useful local URLs after the stack is healthy:

- API: <http://127.0.0.1:8000>
- Prometheus: <http://127.0.0.1:9090>
- Grafana: <http://127.0.0.1:3000> with anonymous local viewer access and the provisioned **Job Runner Platform** dashboard

Try the API:

```bash
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/readyz
curl -X POST http://127.0.0.1:8000/jobs \
  -H 'Content-Type: application/json' \
  -d '{"job_type":"echo","payload":{"message":"hello from compose"}}'
```

Run the public-safe smoke walkthrough after Compose is healthy:

```bash
scripts/demo-smoke.sh
```

The smoke demo creates `echo` and `checksum` jobs, observes `fail_once` retry behaviour, observes `always_fail` dead-letter behaviour, cancels a bounded `sleep` job, and verifies key metrics. See [`docs/demo-smoke.md`](docs/demo-smoke.md).

Stop the local stack:

```bash
docker compose down
# or remove local PostgreSQL/Redis/observability volumes too:
docker compose down -v
```

## Local development

```bash
uv sync --all-groups
uv run pytest
scripts/quality-gate.sh
```

Or use Make:

```bash
make quality
```

Validate Compose without starting containers:

```bash
docker compose config
```

## Configuration

Runtime configuration uses environment variables prefixed with `JOB_RUNNER_`. See [`example.env`](example.env) for public-safe local placeholders. OpenAPI/Swagger/ReDoc are disabled by default and should be explicitly enabled only for local exploration.

| Environment variable | Default | Purpose |
| --- | --- | --- |
| `JOB_RUNNER_APP_NAME` | `job-runner-platform` | FastAPI title and health metadata. |
| `JOB_RUNNER_APP_VERSION` | `0.1.0` | Application version shown in health metadata and OpenAPI when enabled. |
| `JOB_RUNNER_ENVIRONMENT` | `local` | Environment label emitted in health responses and logs. |
| `JOB_RUNNER_LOG_LEVEL` | `INFO` | Structured logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`. |
| `JOB_RUNNER_DOCS_ENABLED` | `false` | Enables `/docs`, `/redoc`, and `/openapi.json` when set to `true`. |
| `JOB_RUNNER_AUTH_ENABLED` | `false` | Enables API key authentication for `/jobs` business endpoints. |
| `JOB_RUNNER_AUTH_API_KEYS` | empty | Comma-separated accepted `X-API-Key` values when API auth is enabled. |
| `JOB_RUNNER_DATABASE_URL` | `postgresql+asyncpg://localhost:5432/job_runner` | Async SQLAlchemy database URL for Alembic and repositories. |
| `JOB_RUNNER_REDIS_URL` | `redis://localhost:6379/0` | Redis URL used by the queue abstraction for job-ID dispatch signals. |
| `JOB_RUNNER_WORKER_ID` | `local-worker-1` | Worker identity recorded on claimed leases and worker logs. |
| `JOB_RUNNER_JOB_LEASE_SECONDS` | `60` | Lease duration assigned when a worker claims a queued job. |
| `JOB_RUNNER_JOB_POLL_SECONDS` | `1` | Redis polling timeout used by the worker loop. |
| `JOB_RUNNER_WORKER_METRICS_ENABLED` | `false` | Enables the worker's lightweight Prometheus metrics HTTP server. |
| `JOB_RUNNER_WORKER_METRICS_HOST` | `127.0.0.1` | Worker metrics bind host; Compose uses `0.0.0.0` inside the local network. |
| `JOB_RUNNER_WORKER_METRICS_PORT` | `8001` | Worker metrics TCP port. |

`max_attempts` is submitted per job in the `POST /jobs` request body and defaults to `3` in the schema/domain layer.

When `JOB_RUNNER_AUTH_ENABLED=true`, all `/jobs` endpoints require an `X-API-Key` header matching one configured value. System endpoints (`/healthz`, `/readyz`, and `/metrics`) remain unprotected for local orchestration and Prometheus scraping.

## API surface

| Method and path | Behaviour |
| --- | --- |
| `GET /healthz` | Liveness metadata for the API process without dependency checks. |
| `GET /readyz` | PostgreSQL and Redis readiness checks; returns `503` when a dependency is unavailable. |
| `GET /metrics` | Prometheus text exposition for API, queue, worker, and job lifecycle metrics. |
| `POST /jobs` | Creates a queued allowlisted job. Idempotency-key replays return the existing job with `idempotency_replayed: true`. |
| `GET /jobs?limit=50&offset=0&status=queued` | Lists jobs with bounded pagination and an optional status filter. |
| `GET /jobs/{job_id}` | Fetches one job by UUID or returns `404`. |
| `POST /jobs/{job_id}/cancel` | Cancels queued jobs or requests cooperative cancellation for running jobs; terminal jobs return `409`. |

All HTTP responses include `X-Request-ID`. Incoming request IDs are propagated; otherwise the API generates a UUID.

Example job creation body:

```json
{
  "job_type": "checksum",
  "payload": {"text": "hello", "algorithm": "sha256"},
  "max_attempts": 3,
  "idempotency_key": "demo-checksum-1"
}
```

## Safe job handlers

The handler registry contains exactly these allowlisted demo handlers. They validate JSON payloads, never run shell commands or subprocesses, and never read from or mutate the host filesystem.

| Handler | Payload shape | Result/failure behaviour |
| --- | --- | --- |
| `echo` | Any JSON object. | Returns the payload. |
| `sleep` | `{ "seconds": 0.5 }`, bounded from `0` through `5.0`. | Sleeps cooperatively and observes cancellation between short intervals. |
| `checksum` | `{ "text": "hello", "algorithm": "sha256" }`; algorithm is optional and only `sha256` is supported. | Returns a deterministic checksum. |
| `fail_once` | `{}` | Fails on the first attempt, then succeeds on a retry. |
| `always_fail` | `{}` | Always fails safely so dead-letter behaviour can be demonstrated. |

See [`docs/job-handlers.md`](docs/job-handlers.md) for full payload and result details.

## Worker instructions

The worker CLI is available as `job-runner-worker` or `python -m job_runner_platform.worker`. With PostgreSQL and Redis available outside Compose:

```bash
export JOB_RUNNER_DATABASE_URL=postgresql+asyncpg://localhost:5432/job_runner
export JOB_RUNNER_REDIS_URL=redis://localhost:6379/0
uv run alembic upgrade head
uv run job-runner-worker          # long-running worker
uv run job-runner-worker --once   # process at most one dispatch signal, then exit
```

The worker loop:

1. recovers stale `running` leases,
2. polls Redis for a persisted job ID,
3. claims a queued row in PostgreSQL with a worker lease,
4. runs only the allowlisted handler,
5. records success, retry, dead-letter, or cancellation state in PostgreSQL, and
6. safely ignores duplicate or obsolete queue messages.

`SIGINT` and `SIGTERM` request a cooperative stop between jobs. If worker metrics are enabled with `JOB_RUNNER_WORKER_METRICS_ENABLED=true`, the worker exposes Prometheus metrics on `JOB_RUNNER_WORKER_METRICS_HOST:JOB_RUNNER_WORKER_METRICS_PORT`. Docker Compose enables this on port `8001` for Prometheus scraping.

## Observability

- Structured API and worker logs are JSON.
- `X-Request-ID` is propagated on every HTTP response.
- `GET /readyz` reports PostgreSQL and Redis readiness separately.
- `GET /metrics` exposes Prometheus metrics without requiring database or Redis access.
- Docker Compose includes Prometheus and Grafana provisioning for local demos.

Key implemented metric families include:

- `jobs_created_total`
- `jobs_started_total`
- `jobs_succeeded_total`
- `jobs_failed_total`
- `jobs_retried_total`
- `jobs_dead_lettered_total`
- `jobs_cancelled_total`
- `job_duration_seconds`
- `api_requests_total`
- `api_request_duration_seconds`
- `worker_polls_total`
- `queue_polls_total`

See [`docs/observability.md`](docs/observability.md) for local Prometheus/Grafana details.

## Testing and quality gates

`scripts/quality-gate.sh` runs the same checks expected before every ticket is committed:

- shell syntax checks for scripts
- `scripts/check-public-safety.sh` for obvious public-safety risks such as committed `.env` files, real-looking secrets, internal hostnames, and locally configured forbidden private terms
- `scripts/check-architecture-boundaries.sh` for obvious route-to-database, route-to-repository, route-to-queue, and route-to-Redis violations
- `uv sync --locked --all-groups`
- Ruff lint checks
- Ruff format checks
- mypy in strict mode
- pytest with coverage

GitHub Actions CI is defined in [`.github/workflows/ci.yml`](.github/workflows/ci.yml). It uses Python 3.12, installs dependencies with uv, runs both guardrails, validates `docker compose config`, applies Alembic migrations against a PostgreSQL service container, and runs Ruff, mypy, and pytest.

Private forbidden-term checks can be configured locally with ignored files such as `.public-safety-forbidden-terms` or via `JOB_RUNNER_PUBLIC_SAFETY_FORBIDDEN_TERMS`. Do not commit private terms.

## Architecture and documentation links

- [`docs/README.md`](docs/README.md) — documentation index.
- [`docs/architecture.md`](docs/architecture.md) — architecture, boundaries, state transitions, reliability model, observability, and limitations.
- [`docs/api-walkthrough.md`](docs/api-walkthrough.md) — curl-based API walkthrough.
- [`docs/operations.md`](docs/operations.md) — local operation, configuration, migrations, readiness, observability, and troubleshooting.
- [`docs/runbook.md`](docs/runbook.md) — operational runbook and failure-mode response notes.
- [`docs/job-handlers.md`](docs/job-handlers.md) — allowlisted handler payloads and result shapes.
- [`docs/demo-smoke.md`](docs/demo-smoke.md) — local smoke demo script documentation.
- [`docs/decisions/README.md`](docs/decisions/README.md) — accepted ADRs for PostgreSQL as source of truth, Redis dispatch signalling, allowlisted handlers, and leases/stale recovery.

## Limitations

- The Docker Compose stack is for local portfolio demos and is not a hardened production deployment.
- Compose and CI use public-safe placeholder configuration, not production secrets.
- Redis dispatch acknowledgement is intentionally simple; a popped signal can be lost before claim, leaving a durable queued row that would need a future reconciliation pass.
- Metrics are process-local; production multi-worker deployments would need environment-specific labels, aggregation, and alerting.
- Worker leases do not heartbeat or extend during work. Demo handlers are bounded, so `JOB_RUNNER_JOB_LEASE_SECONDS` should be longer than expected handler runtime.
- Priority is persisted and validated, but current claiming is primarily FIFO-by-dispatch signal and row state.
- Optional API key auth is lightweight and intended only for local/portfolio demonstration.
