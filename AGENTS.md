You are building `job-runner-platform`, an independent public portfolio project.

The project demonstrates backend and platform engineering through a production-style background job platform.

## Portfolio purpose

This repo should make the maintainer look like an obvious backend/platform engineering candidate.

It must demonstrate:

- FastAPI backend API design
- PostgreSQL persistence and migrations
- Redis-backed queue/dispatch behaviour
- Worker process design
- retries and dead-letter handling
- idempotency keys
- cancellation
- leases / stale job recovery
- structured JSON logging
- request ID propagation
- Prometheus metrics
- health/readiness checks
- Docker Compose local environment
- GitHub Actions CI
- tests, docs, runbooks, and architecture decisions

## Public-safety constraints

This is an independent public portfolio project.

Do not add:

- employer code
- private data
- internal URLs or hostnames
- credentials or tokens
- screenshots of private systems
- non-public architecture
- employer-specific diagrams
- anything implying employer endorsement

Use only public-safe fake data, local placeholder configuration, and generic demo systems.

## Critical safety rule

Do not implement arbitrary shell command execution.

The platform must not run arbitrary user-submitted commands, scripts, Docker containers, Python code strings, subprocesses, or host-level operations.

Jobs must be limited to allowlisted safe built-in demo handlers, such as:

- echo
- sleep
- checksum
- fail_once
- always_fail

If a future ticket appears to require arbitrary command execution, reinterpret it safely as an allowlisted demo handler.

## Technology direction

Use:

- Python 3.12
- FastAPI
- Pydantic / pydantic-settings
- SQLAlchemy asyncio
- Alembic
- PostgreSQL
- Redis
- prometheus-client
- uv
- Ruff
- mypy strict mode
- pytest
- Docker Compose
- GitHub Actions

Prefer a `src/` layout.

## Architecture boundaries

Keep clear layers:

```text
routes -> schemas -> services -> repositories -> database / queue / cache
worker -> services -> repositories -> database / queue

Rules:

Routes should be thin.
Schemas should validate API input/output.
Services should contain business workflow.
Repositories should own database access.
Queue abstractions should hide Redis details.
Worker handlers should be allowlisted and testable.
No database queries in route functions.
No Redis calls in route functions.
No arbitrary subprocess execution anywhere.
Reliability model

PostgreSQL is the source of truth for jobs.

Redis is used for queue/dispatch signalling.

The system should handle:

job creation
job fetch/list
job cancellation
idempotent job submission
worker claiming
running status
success
failure
retry
dead-letter after max attempts
stale running job recovery via leases
graceful worker shutdown where practical

Job state should be explicit and documented.

Suggested statuses:

queued
running
succeeded
failed
cancel_requested
cancelled
dead_lettered
Observability

Implement:

GET /healthz
GET /readyz
GET /metrics
structured JSON logs
request ID propagation with X-Request-ID
worker logs with job IDs
Prometheus counters/histograms for:
jobs created
jobs started
jobs succeeded
jobs failed
jobs retried
jobs dead-lettered
jobs cancelled
job duration
API request count/duration if practical
Configuration

Use environment variables with the prefix:

JOB_RUNNER_

Examples:

JOB_RUNNER_APP_NAME
JOB_RUNNER_APP_VERSION
JOB_RUNNER_ENVIRONMENT
JOB_RUNNER_LOG_LEVEL
JOB_RUNNER_DOCS_ENABLED
JOB_RUNNER_AUTH_ENABLED
JOB_RUNNER_AUTH_API_KEYS
JOB_RUNNER_DATABASE_URL
JOB_RUNNER_REDIS_URL
JOB_RUNNER_WORKER_ID
JOB_RUNNER_JOB_LEASE_SECONDS
JOB_RUNNER_JOB_POLL_SECONDS
JOB_RUNNER_MAX_ATTEMPTS

Docs/OpenAPI should be disabled by default unless explicitly enabled for local exploration.

Testing expectations

Every meaningful ticket should add or update tests.

Use fake or in-memory abstractions where useful, but keep integration tests for important database behaviour.

Test:

job creation
idempotency
listing/fetching
cancellation
worker success path
retry path
dead-letter path
stale lease recovery
readiness checks
metrics endpoint
API auth when implemented
invalid job types
unsafe job types rejected
Documentation expectations

Maintain:

README.md
docs/architecture.md
docs/api-walkthrough.md
docs/runbook.md
docs/operations.md
docs/decisions/

Include at least these ADRs:

docs/decisions/0001-postgres-source-of-truth.md
docs/decisions/0002-redis-as-dispatch-signal.md
docs/decisions/0003-allowlisted-demo-job-handlers.md
docs/decisions/0004-leases-and-stale-job-recovery.md
Automation behaviour

When invoked by the build loop:

Read AGENTS.md, BUILD_TICKETS.md, and BUILD_NOTES.md.
Select the lowest-numbered TODO or IN_PROGRESS ticket.
Implement only that ticket.
Do not start future tickets.
Do not broaden scope.
Add/update tests.
Add/update docs if behaviour, setup, architecture, operations, or limitations change.
Run scripts/quality-gate.sh.
Update BUILD_TICKETS.md.
Update BUILD_NOTES.md.
Commit the completed ticket with a conventional commit message.
Leave the working tree clean.

If blocked:

explain the blocker in BUILD_NOTES.md
mark the ticket BLOCKED if appropriate
do not mark it DONE
do not commit broken partial work
leave the working tree clean if possible
Commit style

Use conventional commits:

chore:
feat:
fix:
test:
docs:
refactor:
ci:

Examples:

feat: add job creation API
test: cover retry and dead-letter behaviour
docs: add worker runbook
ci: add quality gate workflow

---


