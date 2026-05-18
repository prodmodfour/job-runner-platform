# BUILD_NOTES.md

## Current state

Tickets 000 through 009 are complete. The repository now has the initial Python 3.12 `src/` package skeleton, uv/hatchling packaging, Ruff, mypy strict mode, pytest, pytest-cov, documentation directories, public-safe example configuration, a reusable quality gate, a FastAPI application shell, explicit job domain/API schemas, PostgreSQL persistence scaffolding with Alembic migrations, an internal repository layer for job persistence/state transitions, a Redis-backed queue abstraction for job-ID dispatch signals, a job service layer for create/get/list/cancel workflows, FastAPI job routes for those workflows, safe allowlisted built-in demo job handlers, and a worker CLI/runtime for claiming and executing queued jobs.

Ticket 009 added:

- A `JobWorkerService` workflow that polls the queue, claims queued jobs through PostgreSQL state transitions, runs only allowlisted built-in handlers, records succeeded/failed outcomes, and safely acknowledges duplicate or obsolete dispatch signals.
- A worker runtime package with cooperative loop control and `WorkerRuntimeConfig` backed by `JOB_RUNNER_WORKER_ID`, `JOB_RUNNER_JOB_LEASE_SECONDS`, and `JOB_RUNNER_JOB_POLL_SECONDS` settings.
- A `job-runner-worker` console script plus `python -m job_runner_platform.worker` entry point, including `--once` for local/manual processing and SIGINT/SIGTERM shutdown handling between jobs.
- Structured worker lifecycle logging with `worker_id`, `job_id`, `job_type`, `attempt`, outcome, and error type fields where applicable.
- Worker runtime tests covering successful echo execution, duplicate dispatch signal safety, and safe handler failure recording.
- README local worker run instructions and updated configuration documentation.

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

- `uv lock` — completed after adding the worker console script.
- `uv run ruff check .` — passed.
- `uv run ruff format --check .` — passed.
- `uv run mypy src tests` — passed.
- `uv run pytest -q` — passed (`59 passed`).

## Public-safety notes

This project is an independent public portfolio project.

Do not add employer code, private data, internal URLs, credentials, screenshots, non-public architecture, or anything implying employer endorsement.

Do not implement arbitrary shell command execution. Jobs must be safe allowlisted demo handlers only.

## Latest cycle notes

- Implemented only the worker runtime required by ticket 009; retry/dead-letter policy, stale lease recovery, cooperative cancellation inside running handlers, readiness checks, metrics, auth, Docker Compose stack, and CI were not introduced.
- Preserved public-safety constraints: the worker invokes the built-in handler registry only and does not run shell commands, subprocesses, containers, user-submitted code, or host-level operations.
- Kept the worker on the intended boundary path: worker runtime -> worker service -> repository/queue -> database/Redis.
- The worker records handler failures as `failed` for now. Ticket 010 is expected to add retry and dead-letter policy on top of this foundation.

## Limitations

The worker can claim queued jobs, run safe handlers, and record success/failure, but failed jobs do not retry yet and are not dead-lettered. Stale lease recovery, cancellation checks during running jobs, `/readyz`, `/metrics`, optional auth, Docker Compose, and CI remain future tickets. Local end-to-end execution currently requires separately managed PostgreSQL and Redis services because the Docker Compose stack is not implemented yet.

## Next recommended ticket

Ticket 010.
