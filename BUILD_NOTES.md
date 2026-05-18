# BUILD_NOTES.md

## Current state

Tickets 000 through 023 are complete. The repository now has the initial Python
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
architecture decision records, a local smoke demo script, and a polished final
README for portfolio review.

Ticket 023 added:

- A rewritten `README.md` opening that clearly frames the project as a
  public-safe backend/platform portfolio implementation using FastAPI,
  PostgreSQL, Redis, worker leases, retries, dead-letter handling, cancellation,
  structured logs, Prometheus metrics, Docker Compose, CI, tests, runbooks, and
  ADRs.
- Explicit README sections for portfolio framing, implemented scope,
  public-safety constraints, out-of-scope work, requirements, quick start,
  local development, configuration, API surface, safe handlers, worker
  instructions, observability, testing/quality gates, architecture links, and
  limitations.
- `tests/test_readme_polish.py`, which asserts the ticket 023 README sections,
  first-screen portfolio signals, documented configuration variables, API
  endpoint coverage, core documentation links, and public-safety boundaries.

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
    (`115 passed`)

Additional validation this cycle:

- `uv run pytest tests/test_readme_polish.py -q` — passed (`5 passed`).
- `uv run ruff check tests/test_readme_polish.py` — passed.
- `uv run ruff format --check tests/test_readme_polish.py` — passed.
- `uv run mypy tests/test_readme_polish.py` — passed.

## Public-safety notes

This project is an independent public portfolio project.

Do not add employer code, private data, internal URLs, credentials, screenshots,
non-public architecture, or anything implying employer endorsement.

Do not implement arbitrary shell command execution. Jobs must be safe
allowlisted demo handlers only.

The README now reiterates the safety boundary in the first screen and in the
public-safety/out-of-scope sections. The ticket did not add runtime behaviour,
new job types, external integrations, secrets, private data, or arbitrary
execution features.

The Compose stack and CI PostgreSQL service use local placeholder values only.
They are development/demo settings, not a production security baseline. The
public-safety guardrail supports private forbidden-term lists via ignored local
files or an environment variable; do not commit those private terms.

## Latest cycle notes

- Implemented only ticket 023; final autonomous review and completion marker
  remain future ticket 024.
- Preserved runtime architecture and job execution behaviour: no route, service,
  repository, queue, worker, handler, migration, Compose, or CI implementation
  code changed for this ticket.
- Preserved public-safety constraints: no employer/private details, external
  secrets, arbitrary user-submitted commands, subprocess job handlers, or host
  filesystem mutation features were added.
- The README now points reviewers to the architecture, operations, runbook, API
  walkthrough, job handler, observability, smoke demo, and ADR documentation.

## Limitations

This ticket was documentation-focused and does not change runtime limitations.

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

Ticket 024.
