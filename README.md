# Job Runner Platform

`job-runner-platform` is an independent public portfolio project that demonstrates backend and platform engineering through a production-style background job platform.

The repository is intentionally public-safe: it uses only generic local configuration, fake demo data, and documented constraints. It is not affiliated with any employer or private system.

## Current status

The repository now includes the initial Python package skeleton, a FastAPI application shell with structured JSON logging, `X-Request-ID` propagation, documentation disabled by default, `GET /healthz`, explicit job domain/API schemas, the initial PostgreSQL jobs table model plus Alembic migration, an internal SQLAlchemy repository layer for job persistence/state transitions, a Redis-backed queue abstraction for job-ID dispatch signals, a job service layer for create/get/list/cancel workflows, FastAPI job routes for those workflows, safe built-in demo job handlers, and a worker CLI/runtime that claims queued jobs with leases, executes allowlisted handlers, retries failures, recovers stale leases, cooperatively cancels running jobs where safe, and dead-letters jobs that exhaust `max_attempts`. Metrics, Docker Compose, and CI will be added in later tickets.

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

Implemented runtime settings:

| Environment variable | Default | Purpose |
| --- | --- | --- |
| `JOB_RUNNER_APP_NAME` | `job-runner-platform` | FastAPI application title and health metadata. |
| `JOB_RUNNER_APP_VERSION` | `0.1.0` | FastAPI/OpenAPI version and health metadata. |
| `JOB_RUNNER_ENVIRONMENT` | `local` | Environment label emitted by health responses and logs. |
| `JOB_RUNNER_LOG_LEVEL` | `INFO` | Root structured logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`). |
| `JOB_RUNNER_DOCS_ENABLED` | `false` | Enables `/docs`, `/redoc`, and `/openapi.json` only when explicitly set to `true`. |
| `JOB_RUNNER_DATABASE_URL` | `postgresql+asyncpg://localhost:5432/job_runner` | Async SQLAlchemy database URL used by Alembic and repositories. |
| `JOB_RUNNER_REDIS_URL` | `redis://localhost:6379/0` | Redis URL used by the queue abstraction for job-ID dispatch signals. |
| `JOB_RUNNER_WORKER_ID` | `local-worker-1` | Worker identity recorded on claimed job leases and worker logs. |
| `JOB_RUNNER_JOB_LEASE_SECONDS` | `60` | Lease duration assigned when a worker claims a queued job. |
| `JOB_RUNNER_JOB_POLL_SECONDS` | `1` | Redis polling timeout used by the worker loop. |

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

Shutdown is cooperative: `SIGINT`/`SIGTERM` ask the worker to stop between jobs. If a safe handler is already running, the worker lets it finish and records the outcome before exiting. Job cancellation is also cooperative: queued jobs are terminally `cancelled`, running jobs become `cancel_requested`, and handlers that can safely pause (currently `sleep`) check for that request between short async intervals before the worker records the terminal `cancelled` state. On handler failure, jobs are requeued while attempts remain and are marked `dead_lettered` after `max_attempts`. Each worker loop also recovers expired `running` leases: jobs with attempts remaining are requeued and re-signalled, while exhausted jobs are marked `dead_lettered`.

See [`docs/decisions/0004-leases-and-stale-job-recovery.md`](docs/decisions/0004-leases-and-stale-job-recovery.md) for the lease recovery design record.

## Database migrations

Alembic is configured at `alembic.ini` with migration scripts in `migrations/`. The initial revision creates the PostgreSQL source-of-truth `jobs` table.

```bash
JOB_RUNNER_DATABASE_URL=postgresql+asyncpg://localhost:5432/job_runner uv run alembic upgrade head
```

A local PostgreSQL service is not yet provided by this repository; Docker Compose arrives in a later ticket.

## API surface

- `GET /healthz` returns liveness metadata for the API process.
- `POST /jobs` creates a queued allowlisted job and returns `201 Created`. If an idempotency key replays an existing submission, the response is `200 OK` with `idempotency_replayed: true`.
- `GET /jobs?limit=50&offset=0&status=queued` lists jobs with bounded pagination and an optional status filter.
- `GET /jobs/{job_id}` returns one job or a clear `404` when it does not exist.
- `POST /jobs/{job_id}/cancel` cancels a queued job or requests cancellation for a running job. Missing jobs return `404`; terminal jobs return `409 Conflict`.
- All HTTP responses include `X-Request-ID`; an incoming value is propagated and a UUID is generated when the header is absent.
- Swagger/ReDoc/OpenAPI routes are disabled by default for safer public-facing defaults.

The job API uses PostgreSQL and Redis through the service, repository, and queue layers. Safe handlers, the worker runtime, retry, dead-letter behaviour, cancellation, and stale lease recovery are implemented and unit-tested, but a local Docker Compose stack is not available yet, so local end-to-end job execution still requires separately managed PostgreSQL and Redis services.

## Quality gate

`scripts/quality-gate.sh` currently runs:

- shell syntax checks for repository scripts
- `uv sync`
- Ruff lint checks
- Ruff format checks
- mypy in strict mode
- pytest with coverage
