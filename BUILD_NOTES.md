# BUILD_NOTES.md

## Current state

Tickets 000 through 014 are complete. The repository now has the initial Python
3.12 `src/` package skeleton, uv/hatchling packaging, Ruff, mypy strict mode,
pytest, pytest-cov, documentation directories, public-safe example
configuration, a reusable quality gate, a FastAPI application shell, explicit
job domain/API schemas, PostgreSQL persistence scaffolding with Alembic
migrations, an internal repository layer for job persistence/state transitions,
a Redis-backed queue abstraction for job-ID dispatch signals, a job service
layer for create/get/list/cancel workflows, FastAPI job routes for those
workflows, safe allowlisted built-in demo job handlers, a worker CLI/runtime,
retry/dead-letter behaviour, lease-based stale job recovery, cooperative worker
cancellation handling, API readiness checks for PostgreSQL and Redis, and
Prometheus metrics exposition.

Ticket 014 added:

- `prometheus-client` as a runtime dependency.
- `GET /metrics` returning Prometheus text exposition without requiring
  PostgreSQL or Redis dependency access.
- A small observability layer with an injectable metrics recorder so services,
  worker logic, and middleware can record metrics without coupling route
  handlers to implementation details.
- API request counters and duration histograms with method/path/status labels.
- Job lifecycle counters for jobs created, started, succeeded, failed, retried,
  dead-lettered, and cancelled.
- A `job_duration_seconds` histogram for worker processing duration of claimed
  job attempts.
- Worker/queue polling counters for process outcomes and dispatch-signal poll
  results.
- Tests covering the metrics endpoint, required metric names, service lifecycle
  metric recording, worker success metrics, retry metrics, and dead-letter
  metrics.
- README and runbook updates documenting the metrics endpoint and key metric
  names.

## Quality gates

Latest run:

- `scripts/quality-gate.sh` — passed
  - shell syntax checks
  - `uv sync --locked --all-groups`
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run mypy src tests`
  - `uv run pytest --cov=job_runner_platform --cov-report=term-missing`

Additional validation this cycle before the full gate:

- `uv run ruff check . && uv run ruff format --check . && uv run mypy src tests && uv run pytest tests/test_metrics.py -q` — passed (`4 passed`).
- `uv run pytest -q` — passed (`77 passed`).

## Public-safety notes

This project is an independent public portfolio project.

Do not add employer code, private data, internal URLs, credentials, screenshots,
non-public architecture, or anything implying employer endorsement.

Do not implement arbitrary shell command execution. Jobs must be safe
allowlisted demo handlers only.

## Latest cycle notes

- Implemented only the Prometheus metrics scope required by ticket 014; optional
  API key authentication, Docker Compose, Prometheus/Grafana scrape/dashboard
  configuration, and CI were not introduced.
- Preserved architecture boundaries: routes expose `/metrics`, middleware
  records API request metrics, services/workers record lifecycle metrics through
  an observability abstraction, repositories still own SQL, and queues still
  hide Redis details.
- Preserved public-safety constraints: metrics record bounded operational counts
  and durations only. No shell commands, subprocesses, containers,
  user-submitted code, host-level operations, secrets, private data, or
  employer-specific details were added.
- PostgreSQL remains the source of truth for job state. Redis remains only a
  job-ID dispatch signal; queue metrics count polling results but do not change
  reliability semantics.

## Limitations

`GET /metrics` exposes in-process Prometheus text metrics, but local Prometheus
scrape configuration, Grafana dashboards, Docker Compose services, optional API
key authentication, and CI remain future tickets. Metrics are process-local; a
multi-process deployment would need an explicit aggregation strategy later.
Readiness checks verify PostgreSQL and Redis connectivity only; they do not
verify that migrations are current or that a worker is running. Local
end-to-end execution currently requires separately managed PostgreSQL and Redis
services because the Docker Compose stack is not implemented yet.

## Next recommended ticket

Ticket 015.
