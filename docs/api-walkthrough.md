# API walkthrough

This walkthrough shows the public HTTP surface for local exploration. It uses only safe allowlisted demo handlers and local placeholder URLs.

Start the local stack first:

```bash
docker compose up --build
```

The API is then available at `http://127.0.0.1:8000`. Compose enables API docs for local exploration, but the application default is to keep `/docs`, `/redoc`, and `/openapi.json` disabled unless `JOB_RUNNER_DOCS_ENABLED=true`.

## System endpoints

### Liveness

```bash
curl -i http://127.0.0.1:8000/healthz
```

Expected behaviour:

- `200 OK`
- JSON body with `status: ok`, app name, app version, and environment
- no PostgreSQL or Redis dependency checks
- `X-Request-ID` response header

### Readiness

```bash
curl -i http://127.0.0.1:8000/readyz
```

Expected behaviour:

- `200 OK` with `status: ready` when PostgreSQL and Redis are reachable
- `503 Service Unavailable` with `status: not_ready` and per-dependency messages when either check fails

Readiness checks use the database and queue abstraction layers; routes do not call SQLAlchemy or Redis directly.

### Metrics

```bash
curl http://127.0.0.1:8000/metrics
```

The response is Prometheus text exposition. Important metric families include:

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

## Authentication

Business endpoints under `/jobs` are unauthenticated by default. When API key auth is enabled:

```text
JOB_RUNNER_AUTH_ENABLED=true
JOB_RUNNER_AUTH_API_KEYS=local-demo-key
```

Requests to `/jobs` must include:

```bash
-H 'X-API-Key: local-demo-key'
```

`/healthz`, `/readyz`, and `/metrics` are intentionally not protected so local orchestrators and Prometheus can probe them.

## Create an echo job

```bash
curl -i -X POST http://127.0.0.1:8000/jobs \
  -H 'Content-Type: application/json' \
  -H 'X-Request-ID: demo-echo-001' \
  -d '{"job_type":"echo","payload":{"message":"hello from the API"}}'
```

Expected behaviour:

- `201 Created`
- `X-Request-ID: demo-echo-001` is propagated
- response body has `idempotency_replayed: false`
- `job.status` is usually `queued` at creation time
- the worker later claims and completes the job with `status: succeeded`

Abbreviated response:

```json
{
  "job": {
    "id": "00000000-0000-4000-8000-000000000000",
    "job_type": "echo",
    "status": "queued",
    "attempts": 0,
    "max_attempts": 3,
    "payload": {"message": "hello from the API"},
    "result": null
  },
  "idempotency_replayed": false
}
```

The UUID above is an example placeholder; use the `id` returned by your local API.

## Fetch one job

```bash
curl -i http://127.0.0.1:8000/jobs/<job-id>
```

Expected behaviour:

- `200 OK` and a full job detail response when the job exists
- `404 Not Found` when the UUID is well-formed but not present
- FastAPI validation error when the path value is not a UUID

After the worker succeeds, an echo job has a result shaped like:

```json
{
  "payload": {"message": "hello from the API"}
}
```

## List jobs

```bash
curl -i 'http://127.0.0.1:8000/jobs?limit=10&offset=0'
curl -i 'http://127.0.0.1:8000/jobs?limit=10&offset=0&status=queued'
curl -i 'http://127.0.0.1:8000/jobs?limit=10&offset=0&status=dead_lettered'
```

The list response contains:

- `items`: the current page of jobs
- `count`: number of returned items
- `limit`: requested page size
- `offset`: requested offset

`limit` is bounded to `1..100`, and `offset` must be non-negative.

## Idempotent submission

Use `idempotency_key` when a client may retry the same create request:

```bash
curl -i -X POST http://127.0.0.1:8000/jobs \
  -H 'Content-Type: application/json' \
  -d '{"job_type":"checksum","idempotency_key":"demo-checksum-001","payload":{"text":"hello","algorithm":"sha256"}}'
```

Repeat the same request. Expected replay behaviour:

- the first request returns `201 Created`
- later requests with the same key return `200 OK`
- `idempotency_replayed` is `true`
- the existing job row is returned
- no duplicate Redis dispatch signal is published by the service

The idempotency key must be 1 to 128 characters and match the configured safe pattern of letters, numbers, dot, underscore, colon, and hyphen.

## Handler examples

All job payloads are JSON objects. Supported job types are exactly:

| Job type | Example body |
| --- | --- |
| `echo` | `{"job_type":"echo","payload":{"message":"hello"}}` |
| `sleep` | `{"job_type":"sleep","payload":{"seconds":1.5}}` |
| `checksum` | `{"job_type":"checksum","payload":{"text":"hello","algorithm":"sha256"}}` |
| `fail_once` | `{"job_type":"fail_once","payload":{}}` |
| `always_fail` | `{"job_type":"always_fail","payload":{},"max_attempts":2}` |

Invalid job types are rejected by schema validation with `422 Unprocessable Entity`. Handler names are identifiers for built-in functions only; they are not shell commands or user-submitted code.

## Observe retry and dead-letter behaviour

Create a `fail_once` job:

```bash
curl -i -X POST http://127.0.0.1:8000/jobs \
  -H 'Content-Type: application/json' \
  -d '{"job_type":"fail_once","payload":{},"max_attempts":3}'
```

Expected behaviour:

1. Worker claims attempt 1 and the handler fails intentionally.
2. The job is requeued because attempts remain.
3. Worker claims attempt 2 and the handler succeeds.
4. Final status becomes `succeeded` with result `{"failed_once": true, "attempt": 2}`.

Create an `always_fail` job:

```bash
curl -i -X POST http://127.0.0.1:8000/jobs \
  -H 'Content-Type: application/json' \
  -d '{"job_type":"always_fail","payload":{},"max_attempts":2}'
```

Expected behaviour:

1. Attempts increment when the worker claims the job.
2. The worker requeues while `attempts < max_attempts`.
3. The final exhausted attempt records a safe error message and moves the job to `dead_lettered`.

## Cancel a job

Queued jobs move directly to terminal `cancelled`:

```bash
curl -i -X POST http://127.0.0.1:8000/jobs/<job-id>/cancel
```

Running jobs move to `cancel_requested`. The `sleep` handler checks for cancellation between short bounded async sleep intervals, so a long enough sleep job can stop cooperatively and finish as `cancelled`.

Terminal jobs cannot be cancelled again:

- missing job: `404 Not Found`
- already terminal job: `409 Conflict`

## Response fields

Job detail responses include the full persisted state:

| Field | Meaning |
| --- | --- |
| `id` | Job UUID. |
| `job_type` | Allowlisted handler name. |
| `status` | Current lifecycle state. |
| `priority` | Validated integer priority, currently persisted for future scheduling. |
| `attempts` | Number of claims started by workers. |
| `max_attempts` | Maximum attempts before dead-letter. |
| `payload` | Original JSON object. |
| `result` | Handler result after success, otherwise `null`. |
| `error_message` | Bounded safe error summary, otherwise `null`. |
| `idempotency_key` | Optional create-request replay key. |
| timestamps | `created_at`, `updated_at`, `queued_at`, `started_at`, `finished_at`. |
| lease fields | `lease_owner` and `lease_expires_at` while running. |

## Error responses

Common API-level errors:

| Scenario | Status |
| --- | --- |
| Invalid request body, invalid job type, invalid status filter, or invalid pagination | `422 Unprocessable Entity` |
| Unknown job UUID | `404 Not Found` |
| Cancelling a terminal job | `409 Conflict` |
| Missing or invalid `X-API-Key` when auth is enabled | `401 Unauthorized` |
| Dependency unavailable on readiness check | `503 Service Unavailable` |

## Safety reminder

The API accepts only allowlisted job types and JSON payloads. It does not accept shell command strings, scripts, container images, file paths to process, or user-provided code.
