# BUILD_NOTES.md

## Current state

Tickets 000 through 024 are complete. The repository now has the initial Python
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
endpoints, a local Docker Compose stack, local Prometheus/Grafana observability
configuration, GitHub Actions CI, automation guardrail scripts, completed core
architecture/operations/runbook/API walkthrough documentation, the required
architecture decision records, a local smoke demo script, a polished final
README for portfolio review, and final review completion markers.

Ticket 024 added:

- A final autonomous review pass against the ticket checklist: arbitrary
  runtime execution APIs, public-safety guardrails, secrets/private-detail
  guardrails, documentation consistency, README/API behaviour alignment, CI
  presence, Docker Compose validation, test coverage, architecture boundaries,
  and public portfolio framing.
- `tests/test_final_review.py`, covering the final completion marker, all ticket
  statuses, absence of obvious arbitrary execution APIs in runtime source,
  exact allowlisted handler registration, and public example/Compose
  configuration alignment with implemented `Settings` fields.
- Removal of the unused `JOB_RUNNER_MAX_ATTEMPTS` placeholder from `example.env`
  and `docker-compose.yml`; `max_attempts` remains an API request field with a
  schema/domain default of `3`, matching README and operations documentation.
- `BUILD_TICKETS.md` updates marking ticket 024 `DONE` and setting
  `AUTOMATION_STATUS: DONE`.

## Quality gates

Latest run:

- `scripts/quality-gate.sh` — passed
  - shell syntax checks
  - `scripts/check-public-safety.sh`
  - `scripts/check-architecture-boundaries.sh`
  - `uv sync --locked --all-groups`
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run mypy src tests`
  - `uv run pytest --cov=job_runner_platform --cov-report=term-missing`
    (`119 passed`)

Additional validation this cycle:

- `bash scripts/check-public-safety.sh` — passed.
- `bash scripts/check-architecture-boundaries.sh` — passed.
- `docker compose config` — passed.
- Runtime-source arbitrary-execution scan for subprocess/os-system/eval/exec
  patterns — passed.
- `uv run pytest tests/test_final_review.py -q` — passed (`4 passed`).
- `uv run ruff check tests/test_final_review.py` — passed.
- `uv run ruff format --check tests/test_final_review.py` — passed after
  formatting.
- `uv run mypy tests/test_final_review.py` — passed.

## Public-safety notes

This project is an independent public portfolio project.

Do not add employer code, private data, internal URLs, credentials, screenshots,
non-public architecture, or anything implying employer endorsement.

Do not implement arbitrary shell command execution. Jobs must be safe
allowlisted demo handlers only.

The final review preserved the runtime safety boundary: no new job types,
external integrations, secrets, private data, arbitrary user-submitted commands,
subprocess job handlers, container execution jobs, or host filesystem mutation
features were added. The only runtime-facing configuration adjustment removed an
unused placeholder variable so public local configuration matches implemented
settings.

The Compose stack and CI PostgreSQL service use local placeholder values only.
They are development/demo settings, not a production security baseline. The
public-safety guardrail supports private forbidden-term lists via ignored local
files or an environment variable; do not commit those private terms.

## Latest cycle notes

- Implemented only ticket 024; no future tickets remain.
- Preserved runtime architecture and job execution behaviour: no route, service,
  repository, queue, worker, handler, migration, CI workflow, observability, or
  API behaviour changes were introduced.
- Confirmed the handler registry remains exactly `echo`, `sleep`, `checksum`,
  `fail_once`, and `always_fail`.
- Confirmed route-layer architecture boundaries with the guardrail script and
  Docker Compose configuration with `docker compose config`.
- Confirmed README and operations documentation align with the implemented
  `max_attempts` model: per-job request field, not environment setting.

## Limitations

Final review does not change runtime limitations.

The Docker Compose stack remains local-only and uses placeholder settings.
Metrics remain process-local, worker leases do not heartbeat, queued-row
reconciliation for lost Redis signals is not implemented, API readiness does not
verify worker availability, and the Grafana dashboard remains intentionally
basic.

The guardrails and final-review tests are intentionally lightweight static
checks. They catch obvious public-safety, arbitrary-execution, configuration,
and route-layering mistakes, but they are not a substitute for human review,
secret scanning services, or full static analysis. The public forbidden-term
check requires terms to be supplied locally through ignored files or
`JOB_RUNNER_PUBLIC_SAFETY_FORBIDDEN_TERMS`; the repository does not commit
private employer-specific terms.

## Next recommended ticket

None. The autonomous build is complete.
