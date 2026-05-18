# BUILD_NOTES.md

## Current state

Tickets 000 through 016 are complete. The repository now has the initial Python
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
endpoints, and a local Docker Compose stack.

Ticket 016 added:

- A multi-stage `Dockerfile` that installs locked runtime dependencies with
  `uv`, includes Alembic migrations, starts the FastAPI app with Uvicorn, runs
  as a non-root `app` user, and defines a `/healthz` container health check.
- `docker-compose.yml` with local-only placeholder configuration for `api`,
  `worker`, `postgres`, `redis`, `prometheus`, and `grafana` services.
- Compose dependency health checks for PostgreSQL, Redis, the API, and worker
  process liveness, with loopback-only host port bindings for local use.
- Automatic Alembic migration execution in the local Compose API container
  before Uvicorn starts, so `docker compose up --build` can run an end-to-end
  local stack.
- A `.dockerignore` to keep virtual environments, caches, local env files, and
  build artifacts out of the container build context.
- Runtime `uvicorn[standard]` dependency for the containerized API server.
- Container configuration tests covering required services, non-root runtime
  posture, local placeholder environment, health checks, and dependency order.
- README updates documenting Docker Compose requirements and quick-start
  commands.

## Quality gates

Latest run:

- `scripts/quality-gate.sh` — passed
  - shell syntax checks
  - `uv sync --locked --all-groups`
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run mypy src tests`
  - `uv run pytest --cov=job_runner_platform --cov-report=term-missing`
    (`85 passed`)

Additional validation this cycle before the full gate:

- `docker compose config` — passed.
- `docker build --check .` — passed.
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src tests && uv run pytest tests/test_container_config.py -q` — passed (`3 passed`).

## Public-safety notes

This project is an independent public portfolio project.

Do not add employer code, private data, internal URLs, credentials, screenshots,
non-public architecture, or anything implying employer endorsement.

Do not implement arbitrary shell command execution. Jobs must be safe
allowlisted demo handlers only.

The Compose stack uses local placeholder values only. The PostgreSQL password
and Grafana defaults are local development placeholders, not production
credentials, and the exposed ports bind to `127.0.0.1`.

## Latest cycle notes

- Implemented only the Dockerfile and Docker Compose scope required by ticket
  016; Prometheus scrape configuration, Grafana provisioning/dashboards, CI,
  automation guardrails, and broader operations docs were not introduced.
- Preserved architecture boundaries: the container stack wires existing API,
  worker, database, and queue components together without moving database or
  Redis access into routes.
- Preserved public-safety constraints: no employer/private details, external
  secrets, arbitrary user-submitted commands, subprocess job handlers, or host
  filesystem mutation features were added.
- The API and worker containers share the same application image; Compose gives
  each service a fixed command and local environment.

## Limitations

The Docker Compose stack is for local development and portfolio demos only. It
uses placeholder local credentials and should not be treated as a production
security baseline. The API container runs Alembic migrations automatically for
local convenience; production deployments would usually run migrations as an
explicit release step. Prometheus and Grafana services are present, but custom
scrape configuration, Grafana provisioning, and dashboards remain future ticket
017. GitHub Actions CI, automation guardrails, broader documentation, and smoke
demo scripts remain future tickets. Metrics are process-local; a multi-process
deployment would need an explicit aggregation strategy later. Readiness checks
verify PostgreSQL and Redis connectivity only; they do not verify that a worker
is running.

## Next recommended ticket

Ticket 017.
