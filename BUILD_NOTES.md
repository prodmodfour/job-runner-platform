# BUILD_NOTES.md

## Current state

Tickets 000 through 022 are complete. The repository now has the initial Python
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
architecture decision records, and a local smoke demo script.

Ticket 022 added:

- `scripts/demo-smoke.sh`, an executable local-only smoke demo that checks API
  health/readiness, creates `echo` and `checksum` jobs, observes `fail_once`
  retry behaviour, observes `always_fail` dead-letter behaviour, cancels a
  running bounded `sleep` job, and verifies key Prometheus metric families.
- `docs/demo-smoke.md`, documenting prerequisites, local-only script settings,
  the demonstrated flow, safety boundaries, and troubleshooting notes.
- README and docs index links to the smoke demo so local portfolio walkthroughs
  can discover it after starting Docker Compose.
- `tests/test_demo_smoke_script.py`, covering script presence/executability,
  required job/metrics/status flows, absence of obvious arbitrary-execution
  shell patterns, and documentation links.

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
    (`110 passed`)

Additional validation this cycle:

- `bash -n scripts/demo-smoke.sh` — passed.
- `uv run pytest tests/test_demo_smoke_script.py -q` — passed (`4 passed`).

## Public-safety notes

This project is an independent public portfolio project.

Do not add employer code, private data, internal URLs, credentials, screenshots,
non-public architecture, or anything implying employer endorsement.

Do not implement arbitrary shell command execution. Jobs must be safe
allowlisted demo handlers only.

The smoke demo submits only public-safe built-in handler names and JSON payloads
through the local API. It does not send shell commands, scripts, container
images, subprocess requests, file paths, or user-provided code as jobs.

The Compose stack and CI PostgreSQL service use local placeholder values only.
They are development/demo settings, not a production security baseline. The
public-safety guardrail supports private forbidden-term lists via ignored local
files or an environment variable; do not commit those private terms.

## Latest cycle notes

- Implemented only ticket 022; final README polish and final autonomous review
  remain future tickets.
- Preserved runtime architecture and job execution behaviour: no route, service,
  repository, queue, worker, handler, migration, Compose, or CI implementation
  code changed for this ticket.
- Preserved public-safety constraints: no employer/private details, external
  secrets, arbitrary user-submitted commands, subprocess job handlers, or host
  filesystem mutation features were added.
- The smoke demo assumes the local Docker Compose stack is already running and
  healthy; it is not wired into the automated quality gate because it requires
  live local PostgreSQL, Redis, API, and worker services.

## Limitations

The smoke demo is a local portfolio walkthrough, not a production validation or
load test. It uses the Compose API URL by default, requires `curl` and `python3`
on the host running it, and depends on a healthy worker to progress queued jobs.
If API key auth is enabled locally, the caller must provide a local demo key with
`JOB_RUNNER_DEMO_API_KEY`.

The Docker Compose stack remains local-only and uses placeholder settings.
Metrics remain process-local, worker leases do not heartbeat, queued-row
reconciliation for lost Redis signals is not implemented, API readiness does not
verify worker availability, and the Grafana dashboard remains intentionally
basic.

The guardrails are intentionally lightweight static checks. They catch obvious
public-safety and route-layering mistakes, but they are not a substitute for
human review, secret scanning services, or full static analysis. The public
forbidden-term check requires terms to be supplied locally through ignored files
or `JOB_RUNNER_PUBLIC_SAFETY_FORBIDDEN_TERMS`; the repository does not commit
private employer-specific terms.

## Next recommended ticket

Ticket 023.
