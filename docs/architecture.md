# Architecture

`job-runner-platform` is a public-safe portfolio implementation of a production-style background job platform. It demonstrates an API process, durable job state in PostgreSQL, Redis-backed dispatch signalling, and a separate worker process while intentionally limiting execution to safe built-in demo handlers.

The platform never treats a job type as a shell command, script, container image, Python code string, or host-level operation. Job execution is restricted to the allowlisted handlers documented in [job-handlers.md](job-handlers.md).

## System context

```text
HTTP clients
  |
  v
FastAPI API process
  |-- /healthz, /readyz, /metrics
  |-- /jobs business endpoints
  |
  | persists job rows
  v
PostgreSQL <-----------------------------+
  ^                                      |
  | claims, state transitions, leases    |
  |                                      |
Worker process                           |
  |                                      |
  | polls job ID dispatch signals        |
  v                                      |
Redis list ------------------------------+
```

PostgreSQL is the durable source of truth for jobs. Redis is a wake-up signal that carries job UUIDs only. A worker must claim the PostgreSQL row before running a handler, so duplicate or stale Redis messages do not cause duplicate state transitions.

## Code boundaries

The codebase follows the required layering boundary:

```text
routes -> schemas -> services -> repositories -> database / queue
worker -> services -> repositories -> database / queue
```

Current module responsibilities:

| Layer | Modules | Responsibility |
| --- | --- | --- |
| Routes | `job_runner_platform.api.routes.*` | Thin FastAPI handlers, dependency injection, HTTP status mapping. No direct SQLAlchemy or Redis calls. |
| Schemas | `job_runner_platform.api.schemas` | Pydantic request/response validation, public API shape, JSON payload checks. |
| Services | `job_runner_platform.services.*` | Business workflows for job creation, cancellation, readiness, worker processing, retry, dead-letter, and stale recovery. |
| Repositories | `job_runner_platform.repositories.jobs` | SQLAlchemy reads/writes and row-level state transitions for the `jobs` table. |
| Database | `job_runner_platform.database.*`, `migrations/` | Async engine/session setup, models, readiness probe, Alembic migrations. |
| Queue | `job_runner_platform.queues.*` | Redis/in-memory queue abstraction for job ID dispatch signals. |
| Handlers | `job_runner_platform.handlers.*` | Safe allowlisted demo job handlers. No arbitrary command execution. |
| Worker | `job_runner_platform.worker.*` | CLI and long-running loop that delegates business work to services. |
| Observability | `job_runner_platform.observability.*`, `logging.py` | Prometheus metrics, worker metrics server, structured JSON logging, request IDs. |

The guardrail script `scripts/check-architecture-boundaries.sh` statically checks for obvious route-layer violations.

## Job data model

The PostgreSQL `jobs` table stores the durable state required to recover work after API, worker, Redis, or process failures:

- UUID primary key
- allowlisted `job_type`
- explicit `status`
- integer `priority`
- JSON `payload` and nullable JSON `result`
- bounded nullable `error_message`
- `attempts` and `max_attempts`
- nullable `idempotency_key` with a unique partial index
- nullable `lease_owner` and `lease_expires_at`
- `created_at`, `updated_at`, `queued_at`, `started_at`, `finished_at`

Indexes cover status filtering, creation-time listing, idempotency lookup, and stale lease discovery.

## Job lifecycle

Jobs start as `queued` and then move through explicit states:

```text
queued
  | worker claims row and sets lease
  v
running
  | success
  v
succeeded

running
  | retryable handler failure or stale lease with attempts remaining
  v
queued

running
  | exhausted attempts or stale lease with no attempts remaining
  v
dead_lettered

queued
  | cancellation request before claim
  v
cancelled

running
  | cancellation request
  v
cancel_requested
  | worker observes request cooperatively
  v
cancelled
```

The `failed` status is part of the explicit domain model for terminal failure state transitions. The current worker retry policy does not normally stop in `failed`: failed attempts are requeued while attempts remain and are moved to `dead_lettered` when attempts are exhausted.

Terminal statuses are `succeeded`, `failed`, `cancelled`, and `dead_lettered`.

## Submission and idempotency

`POST /jobs` validates the requested job type through the schema/service layer, persists a `queued` row, and publishes the job UUID to Redis. When a caller supplies an `idempotency_key`, the service first looks up an existing row with that key. A replay returns the existing job with `idempotency_replayed: true` and does not publish another dispatch signal.

This keeps job creation durable even if Redis is temporarily duplicated or workers receive the same UUID more than once.

## Queue design

Redis is intentionally a dispatch signal, not the source of truth. The Redis implementation uses one list key:

- `LPUSH` publishes a persisted job UUID.
- `RPOP` or `BRPOP` polls for the next job UUID.
- `acknowledge(job_id)` is a no-op because Redis list messages are removed when popped.

Duplicate signals are safe because worker execution is gated by `claim_queued_job(...)` in PostgreSQL. If the row is already running, terminal, cancelled, or missing, the worker acknowledges or ignores the message and does not run a handler.

Known trade-off: if a worker pops a Redis signal and crashes before claiming the job, the durable PostgreSQL row remains `queued` but the signal can be lost. Retry and stale recovery paths publish fresh signals, and a future reconciliation pass could re-signal old queued rows if needed.

## Worker processing

On each loop iteration the worker:

1. Recovers stale `running` jobs whose leases have expired.
2. Polls Redis for one job UUID.
3. Attempts to claim the `queued` row in PostgreSQL.
4. Runs exactly one allowlisted built-in handler.
5. Records success, retry, cancellation, or dead-letter state in PostgreSQL.
6. Emits structured JSON logs and Prometheus metrics.

The CLI is available as `job-runner-worker` or `python -m job_runner_platform.worker`. Shutdown is cooperative: `SIGINT` and `SIGTERM` stop the loop between jobs, and an in-flight safe handler is allowed to finish and persist its outcome.

## Retry and dead-letter behaviour

Claiming a job increments `attempts`. Handler failures are recorded as bounded error messages without storing stack traces in the job row.

- If `attempts < max_attempts`, the worker requeues the job, clears the lease, publishes a fresh Redis signal, increments retry metrics, and leaves the error message for visibility.
- If `attempts >= max_attempts`, the worker clears the lease, records `finished_at`, and marks the job `dead_lettered`.

`fail_once` demonstrates retry success. `always_fail` demonstrates dead-letter behaviour.

## Cancellation

Cancellation is persisted in PostgreSQL:

- `queued` jobs move directly to terminal `cancelled`.
- `running` jobs move to `cancel_requested`.
- terminal jobs return a `409 Conflict` from the API.

Workers pass a cancellation check into handlers. The `sleep` handler observes cancellation between short bounded `asyncio.sleep` intervals. After a handler returns, the worker checks cancellation again before recording success or retry so a late request can still win safely.

## Leases and stale recovery

Worker claims set `lease_owner` and `lease_expires_at`. A worker loop explicitly finds `running` rows with expired leases:

- Attempts remaining: requeue the job, clear the lease, store a `StaleLeaseRecovery` error, and publish a new Redis signal.
- No attempts remaining: mark the job `dead_lettered`, clear the lease, and record `finished_at`.

Leases prevent permanently stranded jobs after worker crashes. They are not heartbeats; the current design relies on bounded demo handlers and a lease duration longer than expected handler runtime.

## Observability

The API provides:

- `GET /healthz` for process liveness without dependency checks.
- `GET /readyz` for PostgreSQL and Redis readiness.
- `GET /metrics` for Prometheus text exposition.

Structured logs are JSON and include request IDs for API traffic. All HTTP responses include `X-Request-ID`; an incoming value is propagated and a UUID is generated when absent. Worker logs include `worker_id`, `job_id`, handler type, attempt, and outcome where applicable.

Prometheus metrics include job lifecycle counters, job duration, API request counts/duration, worker polling, and queue polling. In Docker Compose, Prometheus scrapes the API at `api:8000/metrics` and the worker at `worker:8001/metrics`; Grafana provisions a basic local dashboard.

## Public-safety and security posture

The project is designed for public portfolio review and local demos:

- no employer code or private architecture
- no committed credentials or private data
- local placeholder configuration only
- API docs disabled by default unless explicitly enabled
- optional API key authentication for `/jobs` endpoints
- health, readiness, and metrics endpoints intentionally unprotected for local orchestration and scraping
- no arbitrary shell command, subprocess, container, file mutation, or user-code execution in job handlers

This is not a production security baseline. Production deployments would need environment-specific secret management, authentication/authorization, network policy, TLS, alerting, backup policy, and migration controls.

## Known limitations

- Redis list acknowledgement is intentionally simple; a popped signal can be lost before claim, leaving a durable queued row that needs a future reconciliation pass.
- Metrics are process-local. Multi-worker production deployments would need labels, aggregation, and alerting tailored to the environment.
- Leases do not heartbeat or extend during long work. Demo handlers are bounded, and `JOB_RUNNER_JOB_LEASE_SECONDS` should be longer than expected handler runtime.
- Priority is persisted and validated, but current listing/claiming behaviour is still primarily FIFO-by-dispatch signal and row state.
- The Docker Compose stack is for local demos, not hardened production operation.
- Optional API key auth is intentionally lightweight and suitable only for portfolio/local demonstration.
