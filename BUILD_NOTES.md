# BUILD_NOTES.md

## Current state

Tickets 000 through 015 are complete. The repository now has the initial Python
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
Prometheus metrics exposition, and optional API key authentication for business
job endpoints.

Ticket 015 added:

- `JOB_RUNNER_AUTH_ENABLED` and `JOB_RUNNER_AUTH_API_KEYS` settings using the
  existing `JOB_RUNNER_` configuration prefix.
- A small FastAPI API-key dependency that checks `X-API-Key` with constant-time
  comparisons when auth is enabled.
- Business endpoint protection for `/jobs` routes only; `/healthz`, `/readyz`,
  and `/metrics` remain unprotected for liveness, readiness, and Prometheus
  scraping.
- Tests covering auth disabled, missing API key, invalid API key, valid API key,
  settings parsing, and unprotected system endpoints.
- README updates documenting auth configuration and API behaviour.

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

- `uv run ruff check . && uv run ruff format --check . && uv run mypy src tests && uv run pytest tests/test_api_auth.py tests/test_api_app.py -q` — passed (`11 passed`).
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src tests && uv run pytest -q` — passed (`82 passed`).

## Public-safety notes

This project is an independent public portfolio project.

Do not add employer code, private data, internal URLs, credentials, screenshots,
non-public architecture, or anything implying employer endorsement.

Do not implement arbitrary shell command execution. Jobs must be safe
allowlisted demo handlers only.

## Latest cycle notes

- Implemented only the optional API key authentication scope required by ticket
  015; Docker Compose, Prometheus/Grafana scrape/dashboard configuration, CI,
  automation guardrails, and broader docs tickets were not introduced.
- Preserved architecture boundaries: auth is an API-layer dependency applied to
  business job routes, routes remain thin, repositories still own SQL, and queue
  abstractions still hide Redis details.
- Preserved public-safety constraints: test/configuration keys are local demo
  placeholders only. No shell commands, subprocesses, containers,
  user-submitted code, host-level operations, real credentials, private data, or
  employer-specific details were added.
- System endpoints remain accessible without API keys so orchestrators and
  Prometheus can call `/healthz`, `/readyz`, and `/metrics` even when business
  API authentication is enabled.

## Limitations

API key authentication is intentionally simple and optional: it protects the
current `/jobs` business endpoints only when enabled and uses comma-separated
static keys from environment configuration. It does not provide user identity,
roles, key rotation APIs, or per-key auditing. Docker Compose, local
Prometheus/Grafana configuration, GitHub Actions CI, and automation guardrails
remain future tickets. Metrics are process-local; a multi-process deployment
would need an explicit aggregation strategy later. Readiness checks verify
PostgreSQL and Redis connectivity only; they do not verify that migrations are
current or that a worker is running. Local end-to-end execution currently
requires separately managed PostgreSQL and Redis services because the Docker
Compose stack is not implemented yet.

## Next recommended ticket

Ticket 016.
