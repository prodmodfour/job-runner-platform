# BUILD_NOTES.md

## Current state

Tickets 000 through 017 are complete. The repository now has the initial Python
3.12 `src/` package skeleton, uv/hatchling packaging, Ruff, mypy strict mode,
pytest, pytest-cov, documentation directories, public-safe example
configuration, a reusable quality gate, a FastAPI application shell, explicit
job domain/API schemas, PostgreSQL persistence scaffolding with Alembic
migrations, an internal repository layer for job persistence/state transitions,
a Redis-backed queue abstraction for job-ID dispatch signals, a job service
layer for create/get/list/cancel workflows, FastAPI job routes for those
workflows, safe allowlisted built-in demo job handlers, a worker CLI/runtime,
retry/dead-letter behaviour, lease-based stale job recovery, cooperative worker
cancellation handling, API readiness checks for PostgreSQL and Redis,
Prometheus metrics exposition, optional API key authentication for business job
endpoints, a local Docker Compose stack, and local Prometheus/Grafana
observability configuration.

Ticket 017 added:

- `observability/prometheus/prometheus.yml` with local scrape jobs for the API
  (`api:8000/metrics`) and worker (`worker:8001/metrics`) containers.
- A lightweight optional worker metrics HTTP server controlled by
  `JOB_RUNNER_WORKER_METRICS_ENABLED`, `JOB_RUNNER_WORKER_METRICS_HOST`, and
  `JOB_RUNNER_WORKER_METRICS_PORT`.
- Docker Compose wiring that enables the worker metrics server on the internal
  worker port `8001`, mounts Prometheus configuration, mounts Grafana
  provisioning files, and enables anonymous local Grafana viewer access.
- Grafana provisioning for a Prometheus data source and a basic **Job Runner
  Platform** dashboard with panels for job lifecycle counters, API request
  rate/latency, worker polling outcomes, and job duration.
- `docs/observability.md` documenting local observability URLs, scrape targets,
  dashboard coverage, and local limitations.
- README, runbook, example environment, and docs index updates covering the new
  observability setup.
- Tests for Prometheus/Grafana configuration, Docker Compose observability
  mounts, worker metrics settings, dashboard JSON, and the worker metrics HTTP
  server.

## Quality gates

Latest run:

- `scripts/quality-gate.sh` — passed
  - shell syntax checks
  - `uv sync --locked --all-groups`
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run mypy src tests`
  - `uv run pytest --cov=job_runner_platform --cov-report=term-missing`
    (`90 passed`)

Additional validation this cycle before the full gate:

- `docker compose config` — passed.
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src tests && uv run pytest tests/test_metrics.py tests/test_observability_config.py tests/test_api_app.py -q` — passed (`15 passed`).

## Public-safety notes

This project is an independent public portfolio project.

Do not add employer code, private data, internal URLs, credentials, screenshots,
non-public architecture, or anything implying employer endorsement.

Do not implement arbitrary shell command execution. Jobs must be safe
allowlisted demo handlers only.

The Compose stack uses local placeholder values only. The PostgreSQL password
and Grafana anonymous viewer configuration are local development/demo settings,
not a production security baseline, and the exposed host ports bind to
`127.0.0.1`.

## Latest cycle notes

- Implemented only the Prometheus/Grafana configuration scope required by
  ticket 017; GitHub Actions CI, automation guardrails, broader architecture and
  operations docs, ADR completion, smoke/demo scripts, and final README polish
  remain future tickets.
- Preserved architecture boundaries: routes remain thin, database access stays
  in repositories/database helpers, Redis access stays behind queue
  abstractions, and the worker metrics endpoint exposes only process metrics.
- Preserved public-safety constraints: no employer/private details, external
  secrets, arbitrary user-submitted commands, subprocess job handlers, or host
  filesystem mutation features were added.
- Prometheus scrapes separate API and worker processes in Compose so
  process-local API and worker metrics can both appear in the local dashboard.

## Limitations

The Docker Compose stack is for local development and portfolio demos only. It
uses placeholder local credentials and should not be treated as a production
security baseline. The API container runs Alembic migrations automatically for
local convenience; production deployments would usually run migrations as an
explicit release step. The Grafana dashboard is intentionally basic and is not a
production alerting baseline. Metrics remain process-local; the current Compose
configuration scrapes one API container and one worker container separately, and
a multi-process or multi-worker deployment would need deployment-specific
labels, aggregation, and alerting. GitHub Actions CI, automation guardrails,
broader documentation, and smoke demo scripts remain future tickets. Readiness
checks verify PostgreSQL and Redis connectivity only; they do not verify that a
worker is running.

## Next recommended ticket

Ticket 018.
