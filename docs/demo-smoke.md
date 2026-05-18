# Local smoke demo

`scripts/demo-smoke.sh` runs a public-safe end-to-end walkthrough against the local API and worker stack. It submits only the allowlisted demo job types and never sends shell commands, scripts, container images, subprocess requests, file paths, or user-provided code as jobs.

## Prerequisites

Start the local Docker Compose stack in another terminal:

```bash
docker compose up --build
```

Wait until the API and worker are healthy. The script requires only local services from the Compose stack plus `curl` and `python3` on the host running the script.

Compose disables API key authentication by default. If you enable auth for a local experiment, provide a local demo key to the script with `JOB_RUNNER_DEMO_API_KEY`; no external secret service is required.

## Run

```bash
scripts/demo-smoke.sh
```

Optional local-only settings:

| Variable | Default | Purpose |
| --- | --- | --- |
| `JOB_RUNNER_DEMO_API_BASE_URL` | `http://127.0.0.1:8000` | API base URL to target. |
| `JOB_RUNNER_DEMO_POLL_TIMEOUT_SECONDS` | `45` | Integer number of seconds to wait for each expected job state. |
| `JOB_RUNNER_DEMO_POLL_INTERVAL_SECONDS` | `0.5` | Delay between status polls. |
| `JOB_RUNNER_DEMO_API_KEY` | empty | Optional `X-API-Key` value for local auth-enabled demos. |

## What the script demonstrates

The smoke demo verifies `/healthz` and `/readyz`, then exercises the job lifecycle through the public API:

1. Creates an `echo` job and waits for `succeeded`.
2. Creates a `checksum` job and waits for `succeeded`.
3. Creates a `fail_once` job with `max_attempts: 3`, waits for final `succeeded`, and confirms a retry happened by checking `attempts >= 2`.
4. Creates an `always_fail` job with `max_attempts: 2`, waits for `dead_lettered`, and confirms an error message was recorded.
5. Creates a bounded `sleep` job, waits until it is `running`, calls the cancellation endpoint, and waits for terminal `cancelled`.
6. Fetches `/metrics` and checks that key Prometheus job lifecycle metric families are present, including retry, dead-letter, cancellation, and duration metrics.

The script prints the job IDs it created so you can inspect them afterward:

```bash
curl http://127.0.0.1:8000/jobs/<job-id>
```

## Troubleshooting

- If readiness is not `ready`, check `docker compose ps` and `docker compose logs --tail=100 api worker postgres redis`.
- If jobs remain `queued`, confirm the `worker` service is healthy and watching Redis/PostgreSQL.
- If the `sleep` cancellation times out, the worker may not have started the job; inspect worker logs and rerun the script against a healthy stack.
- For a clean local demo state, stop the stack with `docker compose down -v` and start it again.
