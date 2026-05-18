# Job Runner Platform

`job-runner-platform` is an independent public portfolio project that demonstrates backend and platform engineering through a production-style background job platform.

The repository is intentionally public-safe: it uses only generic local configuration, fake demo data, and documented constraints. It is not affiliated with any employer or private system.

## Current status

The repository now includes the initial Python package skeleton, public-safety and architecture guardrail scripts, a FastAPI application shell with structured JSON logging, `X-Request-ID` propagation, documentation disabled by default, optional API key authentication for business endpoints, `GET /healthz`, `GET /readyz` dependency checks for PostgreSQL and Redis, `GET /metrics` Prometheus exposition, explicit job domain/API schemas, the initial PostgreSQL jobs table model plus Alembic migration, an internal SQLAlchemy repository layer for job persistence/state transitions, a Redis-backed queue abstraction for job-ID dispatch signals, a job service layer for create/get/list/cancel workflows, FastAPI job routes for those workflows, safe built-in demo job handlers, and a worker CLI/runtime that claims queued jobs with leases, executes allowlisted handlers, retries failures, recovers stale leases, cooperatively cancels running jobs where safe, and dead-letters jobs that exhaust `max_attempts`. A local Docker Compose stack runs the API, worker, PostgreSQL, Redis, Prometheus, and Grafana services with local scrape configuration, Grafana provisioning, and a basic dashboard. GitHub Actions CI mirrors the local quality checks, runs the guardrails, and validates Docker Compose plus Alembic migrations against a PostgreSQL service container.

## Public-safety constraints

This project must not include employer code, private data, internal URLs or hostnames, credentials, tokens, screenshots of private systems, non-public architecture, or anything implying employer endorsement.

The platform must not implement arbitrary shell command execution. Jobs are limited to safe allowlisted demo handlers such as `echo`, `sleep`, `checksum`, `fail_once`, and `always_fail`.

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
- Docker with Docker Compose v2 for the local container stack
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

## Docker Compose quick start

The Compose stack is intended for local portfolio demos only and uses public-safe placeholder configuration. It builds one application image and runs separate API and worker containers alongside PostgreSQL, Redis, Prometheus, and Grafana.

```bash
docker compose up --build
```

The API container runs Alembic migrations before starting Uvicorn. Once the stack is healthy, local endpoints are available at:

- API: <http://127.0.0.1:8000>
- Prometheus: <http://127.0.0.1:9090>
- Grafana: <http://127.0.0.1:3000> with anonymous local viewer access and the provisioned **Job Runner Platform** dashboard

Example API checks:

```bash
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/readyz
curl -X POST http://127.0.0.1:8000/jobs \
  -H 'Content-Type: application/json' \
  -d '{"job_type":"echo","payload":{"message":"hello from compose"}}'
```

Run the local smoke demo after Compose is healthy to create echo/checksum jobs, observe retry and dead-letter behaviour, cancel a sleep job, and check metrics:

```bash
scripts/demo-smoke.sh
```

See [`docs/demo-smoke.md`](docs/demo-smoke.md) for the script flow and optional local-only settings.

Useful local commands:

```bash
docker compose config
docker compose logs -f api worker
docker compose down
docker compose down -v  # also remove local PostgreSQL/Redis/observability volumes
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

Implemented runtime settings:

| Environment variable | Default | Purpose |
| --- | --- | --- |
| `JOB_RUNNER_APP_NAME` | `job-runner-platform` | FastAPI application title and health metadata. |
| `JOB_RUNNER_APP_VERSION` | `0.1.0` | FastAPI/OpenAPI version and health metadata. |
| `JOB_RUNNER_ENVIRONMENT` | `local` | Environment label emitted by health responses and logs. |
| `JOB_RUNNER_LOG_LEVEL` | `INFO` | Root structured logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`). |
| `JOB_RUNNER_DOCS_ENABLED` | `false` | Enables `/docs`, `/redoc`, and `/openapi.json` only when explicitly set to `true`. |
| `JOB_RUNNER_AUTH_ENABLED` | `false` | Enables API key authentication for business job endpoints when set to `true`. |
| `JOB_RUNNER_AUTH_API_KEYS` | empty | Comma-separated list of accepted `X-API-Key` values when API auth is enabled. |
| `JOB_RUNNER_DATABASE_URL` | `postgresql+asyncpg://localhost:5432/job_runner` | Async SQLAlchemy database URL used by Alembic and repositories. |
| `JOB_RUNNER_REDIS_URL` | `redis://localhost:6379/0` | Redis URL used by the queue abstraction for job-ID dispatch signals. |
| `JOB_RUNNER_WORKER_ID` | `local-worker-1` | Worker identity recorded on claimed job leases and worker logs. |
| `JOB_RUNNER_JOB_LEASE_SECONDS` | `60` | Lease duration assigned when a worker claims a queued job. |
| `JOB_RUNNER_JOB_POLL_SECONDS` | `1` | Redis polling timeout used by the worker loop. |
| `JOB_RUNNER_WORKER_METRICS_ENABLED` | `false` | Enables the worker's lightweight Prometheus metrics HTTP server when set to `true`. |
| `JOB_RUNNER_WORKER_METRICS_HOST` | `127.0.0.1` | Bind host for the worker metrics server; Compose overrides this to `0.0.0.0` for Prometheus scraping inside the local network. |
| `JOB_RUNNER_WORKER_METRICS_PORT` | `8001` | TCP port for the worker metrics server. |

Optional API key authentication is disabled by default for local exploration. When `JOB_RUNNER_AUTH_ENABLED=true`, all `/jobs` business endpoints require an `X-API-Key` header that matches one comma-separated value in `JOB_RUNNER_AUTH_API_KEYS`. Missing or invalid keys return `401 Unauthorized`. System endpoints (`/healthz`, `/readyz`, and `/metrics`) remain unprotected so orchestrators and Prometheus can probe them.

The ASGI application factory is `job_runner_platform.api.app:create_app`, and the default app object is `job_runner_platform.api.app:app`.

## Job domain model

The job schema layer defines the public API contract for safe demo jobs. Supported job types are allowlisted values only: `echo`, `sleep`, `checksum`, `fail_once`, and `always_fail`. Job statuses are explicit: `queued`, `running`, `succeeded`, `failed`, `cancel_requested`, `cancelled`, and `dead_lettered`.

Job request/response schemas cover creation, detail views, list pages, cancellation responses, idempotency keys, attempts/max attempts, JSON payload/result fields, errors, timestamps, and lease metadata. The PostgreSQL `jobs` table mirrors those fields, with indexes for status, creation time, idempotency keys, and lease expiry. An internal repository layer owns SQLAlchemy access for creation, fetching/listing, idempotency lookup, cancellation requests, worker claim/complete/fail/dead-letter/requeue transitions, and stale lease lookup. A service layer coordinates repository writes with queue dispatch signals for create/get/list/cancel workflows, and thin FastAPI routes expose those service methods without direct database or Redis calls.

## Safe built-in job handlers

The handler registry contains exactly the allowlisted demo handlers. Handlers validate their JSON payload shape, never run shell commands or subprocesses, and never read from or mutate the host filesystem.

| Handler | Payload shape |
| --- | --- |
| `echo` | Any JSON object, returned as `{ "payload": ... }`. |
| `sleep` | `{ "seconds": 0.5 }`, bounded to `0` through `5.0` seconds; observes cancellation between short async sleep intervals. |
| `checksum` | `{ "text": "hello", "algorithm": "sha256" }`; `algorithm` is optional and only `sha256` is supported. |
| `fail_once` | `{}`; first attempt fails safely, later attempts succeed. |
| `always_fail` | `{}`; always fails safely for future dead-letter demos. |

See [`docs/job-handlers.md`](docs/job-handlers.md) for result shapes and limits.

## Job service layer

`JobService` contains the current business workflow for safe job submission and cancellation. It validates job types against the allowlist, persists new jobs through `JobRepository`, publishes Redis dispatch signals through the queue abstraction, returns existing jobs on idempotency-key replay without publishing duplicate signals, lists jobs with bounded pagination, and rejects cancellation of terminal jobs with a service-layer conflict error. Queued cancellations move directly to `cancelled`; running jobs move to `cancel_requested` so workers can observe the request and transition them to the terminal `cancelled` state.

## Queue dispatch abstraction

Redis is used only as a dispatch signal for persisted job IDs; PostgreSQL remains the source of truth for job state. The queue abstraction supports enqueue, dequeue/poll, acknowledgement, and readiness checks while hiding Redis calls from services/workers. Duplicate job-ID messages are tolerated because workers must claim the job through the repository before running it, so an already-claimed or terminal row is safely ignored.

See [`docs/decisions/0002-redis-as-dispatch-signal.md`](docs/decisions/0002-redis-as-dispatch-signal.md) for the design record.

## Worker runtime

The worker CLI is available as `job-runner-worker` or `python -m job_runner_platform.worker`. It recovers stale leases, polls Redis for job ID dispatch signals, claims queued jobs through the service/repository path, runs only the safe allowlisted built-in handlers, records successful results, requeues retryable failures, marks exhausted jobs `dead_lettered` in PostgreSQL, records requested cancellations as `cancelled`, acknowledges duplicate/obsolete signals safely, and logs lifecycle events with `worker_id` and `job_id` fields.

Local run flow once PostgreSQL and Redis are available:

```bash
export JOB_RUNNER_DATABASE_URL=postgresql+asyncpg://localhost:5432/job_runner
export JOB_RUNNER_REDIS_URL=redis://localhost:6379/0
uv run alembic upgrade head
uv run job-runner-worker          # long-running worker
uv run job-runner-worker --once   # process at most one signal, then exit
```

Set `JOB_RUNNER_WORKER_METRICS_ENABLED=true` to expose the worker process metrics endpoint on `JOB_RUNNER_WORKER_METRICS_HOST:JOB_RUNNER_WORKER_METRICS_PORT`. Docker Compose enables this on the internal worker port `8001` so Prometheus can scrape both API and worker processes.

Shutdown is cooperative: `SIGINT`/`SIGTERM` ask the worker to stop between jobs. If a safe handler is already running, the worker lets it finish and records the outcome before exiting. Job cancellation is also cooperative: queued jobs are terminally `cancelled`, running jobs become `cancel_requested`, and handlers that can safely pause (currently `sleep`) check for that request between short async intervals before the worker records the terminal `cancelled` state. On handler failure, jobs are requeued while attempts remain and are marked `dead_lettered` after `max_attempts`. Each worker loop also recovers expired `running` leases: jobs with attempts remaining are requeued and re-signalled, while exhausted jobs are marked `dead_lettered`.

See [`docs/decisions/0004-leases-and-stale-job-recovery.md`](docs/decisions/0004-leases-and-stale-job-recovery.md) for the lease recovery design record.

## Database migrations

Alembic is configured at `alembic.ini` with migration scripts in `migrations/`. The initial revision creates the PostgreSQL source-of-truth `jobs` table.

```bash
JOB_RUNNER_DATABASE_URL=postgresql+asyncpg://localhost:5432/job_runner uv run alembic upgrade head
```

The Docker Compose API service runs this migration command automatically during local container startup after PostgreSQL is healthy. For manually managed databases, run the command directly from your shell.

## API surface

- `GET /healthz` returns liveness metadata for the API process without dependency checks.
- `GET /readyz` checks PostgreSQL with a minimal readiness query and Redis through the queue abstraction. It returns `200 OK` with `status: ready` when both dependencies are available and `503 Service Unavailable` with per-dependency statuses when either check fails.
- `GET /metrics` returns Prometheus text exposition for API request, worker polling, queue polling, and job lifecycle metrics.
- `/jobs` business endpoints are unauthenticated by default. When `JOB_RUNNER_AUTH_ENABLED=true`, they require `X-API-Key` while `/healthz`, `/readyz`, and `/metrics` remain open.
- `POST /jobs` creates a queued allowlisted job and returns `201 Created`. If an idempotency key replays an existing submission, the response is `200 OK` with `idempotency_replayed: true`.
- `GET /jobs?limit=50&offset=0&status=queued` lists jobs with bounded pagination and an optional status filter.
- `GET /jobs/{job_id}` returns one job or a clear `404` when it does not exist.
- `POST /jobs/{job_id}/cancel` cancels a queued job or requests cancellation for a running job. Missing jobs return `404`; terminal jobs return `409 Conflict`.
- All HTTP responses include `X-Request-ID`; an incoming value is propagated and a UUID is generated when the header is absent.
- Swagger/ReDoc/OpenAPI routes are disabled by default for safer public-facing defaults.

The job API, optional API key authentication, readiness checks, and metrics instrumentation use PostgreSQL and Redis through service, repository/database, queue, and observability layers. Safe handlers, the worker runtime, retry, dead-letter behaviour, cancellation, stale lease recovery, Prometheus metric exposition, and a local Docker Compose stack are implemented and unit-tested.

## Observability metrics

`GET /metrics` exposes Prometheus text metrics without requiring PostgreSQL or Redis access. The endpoint includes API request counters/histograms plus job lifecycle counters and a worker job-duration histogram:

- `jobs_created_total`
- `jobs_started_total`
- `jobs_succeeded_total`
- `jobs_failed_total`
- `jobs_retried_total`
- `jobs_dead_lettered_total`
- `jobs_cancelled_total`
- `job_duration_seconds`

Additional implemented metrics include `api_requests_total`, `api_request_duration_seconds`, `worker_polls_total`, and `queue_polls_total`. In Docker Compose, Prometheus scrapes the API at `api:8000/metrics` and the worker at `worker:8001/metrics`; Grafana provisions a Prometheus data source plus a **Job Runner Platform** dashboard. See [`docs/observability.md`](docs/observability.md) for local observability URLs and dashboard notes.

## Quality gate

`scripts/quality-gate.sh` currently runs:

- shell syntax checks for repository scripts
- `scripts/check-public-safety.sh` for obvious public-safety risks such as real-looking secrets, accidental `.env` files, internal hostnames, and locally configured forbidden private terms
- `scripts/check-architecture-boundaries.sh` for obvious route-to-database, route-to-repository, route-to-queue, and route-to-Redis boundary violations
- `uv sync`
- Ruff lint checks
- Ruff format checks
- mypy in strict mode
- pytest with coverage

Private/employer-specific term checks can be configured locally with the ignored `.public-safety-forbidden-terms` or `.public-safety-denylist` file, or via the `JOB_RUNNER_PUBLIC_SAFETY_FORBIDDEN_TERMS` environment variable. Do not commit private terms.

GitHub Actions CI is defined in `.github/workflows/ci.yml`. It uses Python 3.12, installs dependencies with `uv sync --locked --all-groups`, runs shell syntax checks, runs both guardrail scripts, validates `docker compose config`, applies Alembic migrations against a PostgreSQL service container, and runs the same Ruff, mypy, and pytest checks.
