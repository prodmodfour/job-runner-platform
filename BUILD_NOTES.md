# BUILD_NOTES.md

## Current state

Tickets 000 through 021 are complete. The repository now has the initial Python
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
architecture/operations/runbook/API walkthrough documentation, and the required
architecture decision records.

Ticket 021 added:

- `docs/decisions/0001-postgres-source-of-truth.md`, documenting PostgreSQL as
  the durable source of truth for jobs, idempotency, attempts, leases, results,
  and lifecycle state.
- `docs/decisions/0003-allowlisted-demo-job-handlers.md`, documenting the
  public-safe built-in handler allowlist and the deliberate exclusion of
  arbitrary command, code, container, subprocess, or host-operation execution.
- An updated `docs/decisions/README.md` linking all required ADRs: PostgreSQL
  source of truth, Redis dispatch signal, allowlisted demo handlers, and leases
  with stale recovery.
- Expanded documentation tests in `tests/test_documentation.py` that assert all
  required ADR files exist, include the expected `Status`, `Context`,
  `Decision`, and `Consequences` sections, and are linked from the ADR index.

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
    (`106 passed`)

Additional validation this cycle:

- `uv run pytest tests/test_documentation.py -q` — passed (`5 passed`).

## Public-safety notes

This project is an independent public portfolio project.

Do not add employer code, private data, internal URLs, credentials, screenshots,
non-public architecture, or anything implying employer endorsement.

Do not implement arbitrary shell command execution. Jobs must be safe
allowlisted demo handlers only.

The Compose stack and CI PostgreSQL service use local placeholder values only.
They are development/demo settings, not a production security baseline. The
public-safety guardrail supports private forbidden-term lists via ignored local
files or an environment variable; do not commit those private terms.

## Latest cycle notes

- Implemented only the ADR documentation scope required by ticket 021; smoke/demo
  scripts, final README polish, and final repository review remain future
  tickets.
- Preserved runtime architecture and job execution behaviour: no route,
  service, repository, queue, worker, handler, migration, Compose, or CI
  implementation code changed for this documentation ticket.
- Preserved public-safety constraints: no employer/private details, external
  secrets, arbitrary user-submitted commands, subprocess job handlers, or host
  filesystem mutation features were added.
- Added lightweight ADR coverage tests to keep the required decision records and
  ADR index links from regressing.

## Limitations

The ADRs describe the current local portfolio/demo behaviour; they are not a
production operations, security, backup, or alerting baseline. The Docker Compose
stack remains local-only and uses placeholder settings. Metrics remain
process-local, worker leases do not heartbeat, queued-row reconciliation for lost
Redis signals is not implemented, API readiness does not verify worker
availability, and the Grafana dashboard remains intentionally basic.

The guardrails are intentionally lightweight static checks. They catch obvious
public-safety and route-layering mistakes, but they are not a substitute for
human review, secret scanning services, or full static analysis. The public
forbidden-term check requires terms to be supplied locally through ignored files
or `JOB_RUNNER_PUBLIC_SAFETY_FORBIDDEN_TERMS`; the repository does not commit
private employer-specific terms.

## Next recommended ticket

Ticket 022.
