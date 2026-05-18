# Local observability

The Docker Compose stack includes Prometheus and Grafana for local portfolio demos.
All endpoints bind to `127.0.0.1` on the host and use only local placeholder
configuration.

## URLs

Start the stack:

```bash
docker compose up --build
```

Then use these local URLs:

| Component | URL | Notes |
| --- | --- | --- |
| API metrics | <http://127.0.0.1:8000/metrics> | FastAPI process metrics and API request instrumentation. |
| Prometheus | <http://127.0.0.1:9090> | Scrapes API and worker metrics in the Compose network. |
| Grafana | <http://127.0.0.1:3000> | Anonymous local viewer access is enabled for the provisioned dashboard. |

Grafana provisions a Prometheus data source and a **Job Runner Platform**
dashboard from files under `observability/grafana/`.

## Scrape targets

Prometheus uses `observability/prometheus/prometheus.yml` and scrapes:

- `api:8000/metrics` for API request metrics and API-process job metrics.
- `worker:8001/metrics` for worker polling, queue polling, job lifecycle, and
  job-duration metrics recorded in the worker process.

The worker metrics endpoint is enabled in Compose with:

```text
JOB_RUNNER_WORKER_METRICS_ENABLED=true
JOB_RUNNER_WORKER_METRICS_HOST=0.0.0.0
JOB_RUNNER_WORKER_METRICS_PORT=8001
```

For manual local runs, leave the worker metrics server disabled unless you want
Prometheus to scrape the standalone worker process.

## Dashboard coverage

The dashboard includes starter panels for:

- jobs created, succeeded, failed, retried, cancelled, and dead-lettered
- API request rate and p95 latency
- worker polling outcomes
- p95 job duration

These panels are intentionally basic and public-safe. They are meant to show the
implemented metric names and local observability wiring, not to represent a
production alerting baseline.

## Limitations

Metrics are process-local. Compose scrapes the single API container and the
single worker container separately. A production multi-worker deployment would
need dashboard queries and labels that match that deployment topology, plus an
explicit alerting strategy.
