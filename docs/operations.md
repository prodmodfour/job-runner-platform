# Operations

This document describes how to run and inspect `job-runner-platform` in a local public-safe environment. It is written for the current portfolio/demo implementation, not as a hardened production operations manual.

## Operating principles

- PostgreSQL is the source of truth for job rows, state transitions, attempts, results, errors, idempotency keys, leases, and timestamps.
- Redis carries job UUID dispatch signals only. It does not decide whether a job exists or can run.
- Workers run only allowlisted built-in handlers: `echo`, `sleep`, `checksum`, `fail_once`, and `always_fail`.
- The platform must not execute arbitrary shell commands, subprocesses, containers, scripts, or user-provided code.
- Configuration uses `JOB_RUNNER_` environment variables.
- Local Compose configuration uses placeholder values and is not a production security baseline.

## Local Docker Compose operation

Start the full local stack:

```bash
docker compose up --build
```

Services:

| Service | Purpose | Host URL or port |
| --- | --- | --- |
| `api` | FastAPI app, migrations on startup, `/jobs`, `/healthz`, `/readyz`, `/metrics` | <http://127.0.0.1:8000> |
| `worker` | Long-running job worker and worker metrics server | internal `worker:8001` scrape target |
| `postgres` | Durable job state | `127.0.0.1:5432` |
| `redis` | Dispatch signals | `127.0.0.1:6379` |
| `prometheus` | Local metrics scrape | <http://127.0.0.1:9090> |
| `grafana` | Provisioned local dashboard | <http://127.0.0.1:3000> |

Useful commands:

```bash
docker compose config
docker compose ps
docker compose logs -f api worker
docker compose logs -f postgres redis
docker compose down
docker compose down -v
```

Use `docker compose down -v` only when you want to remove local PostgreSQL, Redis, Prometheus, and Grafana volumes.

## Manual local operation

For non-container development, install dependencies and run checks:

```bash
uv sync --all-groups
scripts/quality-gate.sh
```

Set local dependencies and run migrations after PostgreSQL and Redis are available:

```bash
export JOB_RUNNER_DATABASE_URL=postgresql+asyncpg://localhost:5432/job_runner
export JOB_RUNNER_REDIS_URL=redis://localhost:6379/0
uv run alembic upgrade head
```

Run the API:

```bash
uv run uvicorn job_runner_platform.api.app:app --host 127.0.0.1 --port 8000
```

Run a worker:

```bash
uv run job-runner-worker
```

Process at most one dispatch signal for debugging:

```bash
uv run job-runner-worker --once
```

Enable the standalone worker metrics HTTP server only when needed:

```bash
export JOB_RUNNER_WORKER_METRICS_ENABLED=true
export JOB_RUNNER_WORKER_METRICS_HOST=127.0.0.1
export JOB_RUNNER_WORKER_METRICS_PORT=8001
uv run job-runner-worker
```

## Configuration checklist

Important runtime settings:

| Setting | Operational note |
| --- | --- |
| `JOB_RUNNER_DOCS_ENABLED` | Defaults to `false`; Compose sets it to `true` for local exploration. |
| `JOB_RUNNER_AUTH_ENABLED` | Defaults to `false`; when `true`, `/jobs` endpoints require `X-API-Key`. |
| `JOB_RUNNER_AUTH_API_KEYS` | Comma-separated local demo keys when auth is enabled. Do not commit private values. |
| `JOB_RUNNER_DATABASE_URL` | Async SQLAlchemy URL for PostgreSQL. |
| `JOB_RUNNER_REDIS_URL` | Redis URL for dispatch signals. |
| `JOB_RUNNER_WORKER_ID` | Written to leases and worker logs. Use a unique value per worker. |
| `JOB_RUNNER_JOB_LEASE_SECONDS` | Must be longer than expected handler runtime to avoid premature stale recovery. |
| `JOB_RUNNER_JOB_POLL_SECONDS` | Worker Redis polling timeout. |
| `JOB_RUNNER_WORKER_METRICS_ENABLED` | Enables the worker metrics HTTP server. Compose enables it for Prometheus. |

`max_attempts` is submitted per job through the API request body and defaults to `3` in the schema/domain layer.

## Migrations

Alembic migrations live in `migrations/`. The API container runs:

```bash
alembic upgrade head
```

before starting Uvicorn in the local Compose stack. Manual environments should run migrations explicitly before starting API and worker processes.

Operational expectations:

- migration failures should stop startup rather than serving against an unexpected schema
- PostgreSQL remains the durable state store and should be backed up in any real deployment
- production-style deployments would normally run migrations as an explicit release step instead of inside the API container command

## Health and readiness

Use liveness for process checks:

```bash
curl -i http://127.0.0.1:8000/healthz
```

Use readiness for dependency checks:

```bash
curl -i http://127.0.0.1:8000/readyz
```

Readiness returns per-dependency results for:

- `postgresql`
- `redis`

A worker being absent does not currently make API readiness fail. Readiness only confirms that the API process can reach PostgreSQL and Redis.

## Observability

### Logs

API and worker logs are structured JSON. API logs include request metadata and propagate `X-Request-ID`. Worker lifecycle logs include `worker_id`, `job_id`, attempt number, job type, and outcome where applicable.

Local log command:

```bash
docker compose logs -f api worker
```

### Metrics

API metrics endpoint:

```bash
curl http://127.0.0.1:8000/metrics
```

Prometheus and Grafana URLs in Compose:

- Prometheus: <http://127.0.0.1:9090>
- Grafana: <http://127.0.0.1:3000>

Key metric families:

- `api_requests_total`
- `api_request_duration_seconds`
- `jobs_created_total`
- `jobs_started_total`
- `jobs_succeeded_total`
- `jobs_failed_total`
- `jobs_retried_total`
- `jobs_dead_lettered_total`
- `jobs_cancelled_total`
- `job_duration_seconds`
- `worker_polls_total`
- `queue_polls_total`

Metrics are process-local. In Compose, Prometheus scrapes the API and worker separately.

## Common operating workflows

### Verify the stack is ready

1. `docker compose ps`
2. `curl -i http://127.0.0.1:8000/healthz`
3. `curl -i http://127.0.0.1:8000/readyz`
4. `curl http://127.0.0.1:8000/metrics`
5. Open Prometheus targets at <http://127.0.0.1:9090/targets>

### Submit a safe demo job

```bash
curl -i -X POST http://127.0.0.1:8000/jobs \
  -H 'Content-Type: application/json' \
  -d '{"job_type":"echo","payload":{"message":"hello"}}'
```

Then fetch the returned job ID until the worker marks it `succeeded`.

### Inspect worker progress

Use logs and metrics together:

```bash
docker compose logs -f worker
curl http://127.0.0.1:8000/metrics
```

Look for worker outcomes such as `succeeded`, `retried`, `dead_lettered`, `cancelled`, `claim_skipped`, and `no_message`.

## Failure modes and responses

| Symptom | Likely cause | Response |
| --- | --- | --- |
| `/healthz` fails | API process is not running or not reachable | Check `docker compose ps` and `docker compose logs api`. |
| `/readyz` returns `postgresql` unavailable | PostgreSQL container is unhealthy, migration/startup race, or wrong URL | Check `docker compose ps postgres`, PostgreSQL logs, and `JOB_RUNNER_DATABASE_URL`. |
| `/readyz` returns `redis` unavailable | Redis container is unhealthy or wrong URL | Check `docker compose ps redis`, Redis logs, and `JOB_RUNNER_REDIS_URL`. |
| Jobs stay `queued` | Worker is down, Redis signal was lost, or worker cannot reach dependencies | Check worker logs, worker process health, and Redis/PostgreSQL readiness. |
| Jobs retry repeatedly | Handler is intentionally failing or payload is invalid for the handler | Inspect `error_message`, `attempts`, `max_attempts`, and worker logs. |
| Jobs become `dead_lettered` | Attempts were exhausted through handler failure or stale recovery | Inspect error summaries and decide whether to submit a corrected new job. |
| Jobs stay `running` past expected runtime | Worker crashed or lease duration too short/long relative to handler runtime | Start a worker and allow stale lease recovery to requeue or dead-letter. |
| Cancellation appears delayed | Running cancellation is cooperative | For `sleep`, wait for the next short polling interval; other fast handlers may finish first. |
| Metrics are missing worker activity | Worker metrics server disabled or Prometheus cannot scrape `worker:8001` | Check worker env settings and Prometheus targets. |
| Duplicate Redis messages | Expected tolerated condition | PostgreSQL claim checks skip non-queued rows safely. |

## Backup and data retention notes

The current repository does not implement backup automation, archival, or data retention policies. For a real deployment, PostgreSQL backups and retention rules would be required because job payloads, results, errors, and lifecycle timestamps are durable there.

## Security notes

Local Compose defaults are intentionally convenient:

- placeholder PostgreSQL credentials
- anonymous local Grafana viewer access
- API docs enabled in Compose
- API key auth disabled by default

Do not treat those settings as production-ready. A real deployment would need externally managed secrets, TLS, network controls, stronger authentication/authorization, least-privilege database roles, production Grafana auth, and environment-specific hardening.

## Known limitations

- The platform does not include a queued-row reconciliation command for lost Redis signals.
- Worker leases are fixed-duration and do not heartbeat.
- Handlers are deliberately small public-safe demos, not arbitrary execution plugins.
- Metrics are process-local and need deployment-specific aggregation for multiple workers.
- The included Grafana dashboard is a starter dashboard, not an alerting baseline.
- API readiness does not verify that at least one worker is running.
- Priority is stored but not yet used as a full scheduler.
