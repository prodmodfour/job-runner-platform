# Runbook

This runbook gives practical procedures for the local `job-runner-platform` demo stack. It assumes the platform is running with Docker Compose unless a step says otherwise.

The project is public-safe by design. Do not add private data, credentials, employer-specific details, or arbitrary command execution features while following or extending these procedures.

## Quick triage

When something looks wrong, collect this baseline first:

```bash
docker compose ps
curl -i http://127.0.0.1:8000/healthz
curl -i http://127.0.0.1:8000/readyz
curl http://127.0.0.1:8000/metrics
docker compose logs --tail=100 api worker
```

Interpretation:

- `/healthz` checks only the API process.
- `/readyz` checks PostgreSQL and Redis from the API process.
- `/metrics` should render even when PostgreSQL or Redis is unavailable.
- Worker absence is visible through logs/metrics, not API readiness.

## Job lifecycle reference

Normal state flow:

```text
queued -> running -> succeeded
```

Failure and recovery flow:

```text
running -> queued          # retry or stale recovery with attempts remaining
running -> dead_lettered   # attempts exhausted
```

Cancellation flow:

```text
queued -> cancelled
running -> cancel_requested -> cancelled
```

Terminal states:

- `succeeded`
- `failed`
- `cancelled`
- `dead_lettered`

The current worker usually requeues failed attempts or dead-letters exhausted attempts instead of leaving jobs in `failed`.

## Procedure: API is not healthy

Symptoms:

- `curl -i http://127.0.0.1:8000/healthz` fails
- API container is restarting or absent

Steps:

1. Check container state:

   ```bash
   docker compose ps api
   ```

2. Check API logs:

   ```bash
   docker compose logs --tail=200 api
   ```

3. If logs show migration failure, inspect PostgreSQL health and migration configuration.
4. If logs show import/configuration failure, run the local quality gate:

   ```bash
   scripts/quality-gate.sh
   ```

5. Restart the local stack if the process was interrupted:

   ```bash
   docker compose up --build
   ```

Expected resolution: `/healthz` returns `200 OK` with `status: ok`.

## Procedure: readiness reports PostgreSQL unavailable

Symptoms:

- `/readyz` returns `503`
- response has `checks.postgresql.status: unavailable`

Steps:

1. Check PostgreSQL service state:

   ```bash
   docker compose ps postgres
   docker compose logs --tail=200 postgres
   ```

2. Confirm the API is using the Compose database URL from `docker-compose.yml`.
3. Confirm migrations were attempted in API logs.
4. If this is a disposable local demo, reset local volumes:

   ```bash
   docker compose down -v
   docker compose up --build
   ```

Expected resolution: `/readyz` shows `postgresql` as `ok`.

## Procedure: readiness reports Redis unavailable

Symptoms:

- `/readyz` returns `503`
- response has `checks.redis.status: unavailable`

Steps:

1. Check Redis service state:

   ```bash
   docker compose ps redis
   docker compose logs --tail=200 redis
   ```

2. Confirm `JOB_RUNNER_REDIS_URL` points to the Compose service name inside containers.
3. Restart the stack if Redis was interrupted:

   ```bash
   docker compose up --build
   ```

Expected resolution: `/readyz` shows `redis` as `ok`.

## Procedure: jobs remain queued

Symptoms:

- Jobs are created successfully but stay `queued`
- `jobs_created_total` increases but `jobs_started_total` does not

Likely causes:

- worker is not running
- worker cannot connect to PostgreSQL or Redis
- Redis signal was popped and lost before a claim
- job was cancelled while queued

Steps:

1. Check worker state and logs:

   ```bash
   docker compose ps worker
   docker compose logs --tail=200 worker
   ```

2. Check readiness from the API:

   ```bash
   curl -i http://127.0.0.1:8000/readyz
   ```

3. Check worker polling metrics in Prometheus or `/metrics`:

   - `worker_polls_total`
   - `queue_polls_total`
   - `jobs_started_total`

4. If the worker is down, restart it with the stack:

   ```bash
   docker compose up --build worker
   ```

5. If a signal was lost, the durable queued row remains in PostgreSQL. The current build does not include a queued-row reconciliation command; submit a new demo job or restart from a clean local volume for demos.

Expected resolution: worker logs show `job dispatch signal received`, `job started`, and a terminal or retry outcome.

## Procedure: retry and dead-letter handling

Workers run only allowlisted built-in demo handlers; they never execute shell commands, subprocesses, containers, or user-provided code.

Retry policy:

1. A job starts with `attempts = 0` in `queued` state.
2. Claiming a queued job moves it to `running` and increments `attempts` by one.
3. If the handler succeeds, the worker stores the JSON result, clears prior error state, clears lease fields, records `finished_at`, and marks the job `succeeded`.
4. If the handler fails and `attempts < max_attempts`, the worker stores a safe bounded error message, clears lease fields, requeues the job as `queued`, and publishes a new Redis dispatch signal.
5. If the handler fails and `attempts >= max_attempts`, the worker stores the safe error message, clears lease fields, records `finished_at`, and marks the job `dead_lettered`.

Demo checks:

- Submit `fail_once` with `max_attempts: 3` to observe one retry followed by success.
- Submit `always_fail` with `max_attempts: 2` to observe dead-letter after two attempts.

Troubleshooting repeated retries:

1. Fetch the job:

   ```bash
   curl -i http://127.0.0.1:8000/jobs/<job-id>
   ```

2. Inspect `attempts`, `max_attempts`, `error_message`, and `status`.
3. Check worker logs for the same `job_id`.
4. If the payload is invalid for the handler, submit a new job with corrected payload; current jobs are immutable through the public API.

Error messages stored in jobs are bounded strings with the exception type prefix. Unexpected stack traces are logged by the worker but are not stored in the job row.

## Procedure: cancellation handling

Cancellation is persisted in PostgreSQL; Redis messages remain only dispatch signals.

Queued cancellation:

1. Create a job.
2. Call:

   ```bash
   curl -i -X POST http://127.0.0.1:8000/jobs/<job-id>/cancel
   ```

3. Expected status: `cancelled`.
4. If a stale Redis signal later reaches a worker, the worker fails to claim the non-queued row and skips execution safely.

Running cancellation:

1. Create a `sleep` job with enough time to observe cancellation:

   ```bash
   curl -i -X POST http://127.0.0.1:8000/jobs \
     -H 'Content-Type: application/json' \
     -d '{"job_type":"sleep","payload":{"seconds":5}}'
   ```

2. Cancel it quickly:

   ```bash
   curl -i -X POST http://127.0.0.1:8000/jobs/<job-id>/cancel
   ```

3. Expected flow: `running -> cancel_requested -> cancelled`.
4. Confirm with `GET /jobs/<job-id>` and worker logs.

Notes:

- Cancellation is cooperative, not a host-level kill action.
- The `sleep` handler checks between short bounded async sleep intervals.
- Fast handlers may finish before the cancellation request is observed.
- Terminal jobs return `409 Conflict` for cancellation requests.

## Procedure: stale lease recovery

Workers claim queued jobs by setting `lease_owner` and `lease_expires_at` while moving the job to `running`. The claim increments `attempts`, so a crashed or interrupted attempt is still counted.

Each worker loop performs stale recovery before polling Redis:

1. Find `running` jobs whose `lease_expires_at` is in the past.
2. If `attempts < max_attempts`, store a bounded `StaleLeaseRecovery` error, clear lease fields, move the job back to `queued`, and publish a fresh Redis signal.
3. If `attempts >= max_attempts`, store the same style of error, clear lease fields, record `finished_at`, and mark the job `dead_lettered`.

Operational checks:

- Look for `stale job leases recovered` in worker logs.
- Inspect `error_message` for `StaleLeaseRecovery`.
- Check `jobs_retried_total`, `jobs_failed_total`, and `jobs_dead_lettered_total` metrics.

If stale recovery happens unexpectedly often:

1. Confirm handlers are bounded and not exceeding expected runtime.
2. Increase `JOB_RUNNER_JOB_LEASE_SECONDS` above expected handler duration.
3. Check worker CPU or event-loop starvation in logs/metrics.

A late original worker cannot overwrite a recovered job because repository methods check the current PostgreSQL state before updating rows.

## Procedure: metrics look wrong

Symptoms:

- Prometheus target is down
- Grafana dashboard shows no worker data
- `/metrics` does not include expected counters

Steps:

1. Check API metrics directly:

   ```bash
   curl http://127.0.0.1:8000/metrics
   ```

2. Check Prometheus targets:

   <http://127.0.0.1:9090/targets>

3. Check worker metrics configuration in Compose:

   ```text
   JOB_RUNNER_WORKER_METRICS_ENABLED=true
   JOB_RUNNER_WORKER_METRICS_HOST=0.0.0.0
   JOB_RUNNER_WORKER_METRICS_PORT=8001
   ```

4. Check worker logs for `worker metrics server started`.
5. Generate a new job and observe counters again.

Remember that metrics are process-local. API and worker processes expose separate registries in the Compose stack.

## Procedure: API key authentication failures

Symptoms:

- `/jobs` requests return `401 Unauthorized`
- `/healthz`, `/readyz`, and `/metrics` still work

Steps:

1. Confirm whether auth is enabled:

   ```text
   JOB_RUNNER_AUTH_ENABLED=true
   ```

2. Send a configured local demo key:

   ```bash
   curl -i http://127.0.0.1:8000/jobs \
     -H 'X-API-Key: local-demo-key'
   ```

3. Confirm `JOB_RUNNER_AUTH_API_KEYS` contains the same comma-separated value in the API process environment.

Do not commit real private API keys. Use local placeholder values only.

## Procedure: quality gate failure

The local quality gate runs shell syntax checks, public-safety guardrails, architecture boundary checks, dependency sync, Ruff, mypy, and pytest with coverage:

```bash
scripts/quality-gate.sh
```

Responses by failure type:

| Failure | Response |
| --- | --- |
| Public-safety guardrail | Remove private data, real-looking secrets, internal hostnames, accidental `.env` files, or configured forbidden private terms. |
| Architecture boundary guardrail | Move route-level database/queue work into services/repositories/queue abstractions. |
| Ruff format/check | Run `uv run ruff format .` or fix lint findings. |
| mypy | Preserve strict types in `src` and tests. |
| pytest | Fix the failing behaviour or test fixture. |

## Known limitations

- No queued-row reconciliation command exists yet for a job whose Redis signal was lost before claim.
- No production alerting rules are included.
- No backup/restore automation is included.
- Lease extension/heartbeats are not implemented.
- API readiness does not verify worker availability.
- The local Compose stack uses convenient placeholder settings and should not be used as a production security baseline.
