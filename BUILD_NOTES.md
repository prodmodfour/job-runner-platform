# BUILD_NOTES.md

## Current state

Tickets 000 through 011 are complete. The repository now has the initial Python
3.12 `src/` package skeleton, uv/hatchling packaging, Ruff, mypy strict mode,
pytest, pytest-cov, documentation directories, public-safe example
configuration, a reusable quality gate, a FastAPI application shell, explicit
job domain/API schemas, PostgreSQL persistence scaffolding with Alembic
migrations, an internal repository layer for job persistence/state transitions,
a Redis-backed queue abstraction for job-ID dispatch signals, a job service
layer for create/get/list/cancel workflows, FastAPI job routes for those
workflows, safe allowlisted built-in demo job handlers, a worker CLI/runtime,
retry/dead-letter behaviour, and lease-based stale job recovery.

Ticket 011 added:

- An explicit `JobWorkerService.recover_stale_jobs()` operation that scans
  `running` jobs whose `lease_expires_at` has passed.
- Recovery policy aligned with attempts: stale jobs with remaining attempts are
  requeued, have lease fields cleared, and receive a fresh Redis dispatch
  signal; stale jobs that have exhausted `max_attempts` are marked
  `dead_lettered`.
- Bounded `StaleLeaseRecovery` error messages persisted on recovered jobs so the
  recovery reason is visible without storing stack traces or unsafe data.
- Worker runtime support that runs stale recovery before each queue polling pass.
- Tests covering stale requeue/signalling, stale dead-lettering after attempts
  are exhausted, and runtime recovery before queue polling.
- Documentation in the runbook and
  `docs/decisions/0004-leases-and-stale-job-recovery.md`.

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

- `uv run pytest tests/test_worker_runtime.py -q` — passed (`9 passed`).
- `uv run mypy src tests` — passed.
- `uv run pytest -q` — passed (`65 passed`).

## Public-safety notes

This project is an independent public portfolio project.

Do not add employer code, private data, internal URLs, credentials, screenshots,
non-public architecture, or anything implying employer endorsement.

Do not implement arbitrary shell command execution. Jobs must be safe
allowlisted demo handlers only.

## Latest cycle notes

- Implemented only the lease and stale recovery behaviour required by ticket
  011; cooperative cancellation inside running handlers, readiness checks,
  metrics, auth, Docker Compose stack, and CI were not introduced.
- Preserved public-safety constraints: recovery only updates PostgreSQL job state
  and publishes job UUID dispatch signals; it does not run shell commands,
  subprocesses, containers, user-submitted code, or host-level operations.
- Kept the worker on the intended boundary path: worker runtime -> worker
  service -> repository/queue -> database/Redis.
- Stale recovery treats PostgreSQL as the source of truth. Redis is used only to
  re-signal jobs that are safely moved back to `queued` after the database
  transaction commits.

## Limitations

The worker can claim queued jobs, run safe handlers, retry failures until
`max_attempts`, record success, dead-letter exhausted jobs, and recover expired
`running` leases. Cooperative cancellation checks during running jobs,
`/readyz`, `/metrics`, optional auth, Docker Compose, and CI remain future
tickets. Local end-to-end execution currently requires separately managed
PostgreSQL and Redis services because the Docker Compose stack is not
implemented yet.

## Next recommended ticket

Ticket 012.
