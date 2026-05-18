# BUILD_NOTES.md

## Current state

Tickets 000 through 010 are complete. The repository now has the initial Python 3.12 `src/` package skeleton, uv/hatchling packaging, Ruff, mypy strict mode, pytest, pytest-cov, documentation directories, public-safe example configuration, a reusable quality gate, a FastAPI application shell, explicit job domain/API schemas, PostgreSQL persistence scaffolding with Alembic migrations, an internal repository layer for job persistence/state transitions, a Redis-backed queue abstraction for job-ID dispatch signals, a job service layer for create/get/list/cancel workflows, FastAPI job routes for those workflows, safe allowlisted built-in demo job handlers, a worker CLI/runtime, and retry/dead-letter behaviour.

Ticket 010 added:

- Worker-side retry policy for handler failures: failed attempts are recorded safely, jobs are requeued while `attempts < max_attempts`, and a fresh Redis dispatch signal is published for the retry.
- Dead-letter handling when a failed run exhausts `max_attempts`; jobs move to `dead_lettered`, leases are cleared, and the final safe error message is stored.
- Consistent attempt accounting by relying on the repository claim transition to increment `attempts` exactly once per handler execution.
- Worker process outcomes and logs for `retried` and `dead_lettered` paths, including attempt and max-attempt context.
- Tests covering `fail_once` retry then success, `always_fail` dead-lettering after max attempts, single-attempt dead-lettering, safe error persistence, and recorded-error truncation.
- Runbook documentation for retry/dead-letter operations plus README/docs updates reflecting implemented retry behaviour.

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

- `uv run pytest tests/test_worker_runtime.py -q` — passed (`5 passed`).
- `uv run ruff check .` — passed.
- `uv run ruff format --check .` — passed.
- `uv run mypy src tests` — passed.
- `uv run pytest -q` — passed (`62 passed`).

## Public-safety notes

This project is an independent public portfolio project.

Do not add employer code, private data, internal URLs, credentials, screenshots, non-public architecture, or anything implying employer endorsement.

Do not implement arbitrary shell command execution. Jobs must be safe allowlisted demo handlers only.

## Latest cycle notes

- Implemented only the retry and dead-letter policy required by ticket 010; stale lease recovery, cooperative cancellation inside running handlers, readiness checks, metrics, auth, Docker Compose stack, and CI were not introduced.
- Preserved public-safety constraints: retries invoke only the built-in handler registry and do not run shell commands, subprocesses, containers, user-submitted code, or host-level operations.
- Kept the worker on the intended boundary path: worker runtime -> worker service -> repository/queue -> database/Redis.
- Failed attempts remain durable in PostgreSQL via bounded error messages; retry scheduling uses Redis only as a dispatch signal after the database row has been requeued.

## Limitations

The worker can claim queued jobs, run safe handlers, retry failures until `max_attempts`, record success, and dead-letter exhausted jobs. Stale lease recovery, cancellation checks during running jobs, `/readyz`, `/metrics`, optional auth, Docker Compose, and CI remain future tickets. Local end-to-end execution currently requires separately managed PostgreSQL and Redis services because the Docker Compose stack is not implemented yet.

## Next recommended ticket

Ticket 011.
