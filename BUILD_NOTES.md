# BUILD_NOTES.md

## Current state

Tickets 000 through 012 are complete. The repository now has the initial Python
3.12 `src/` package skeleton, uv/hatchling packaging, Ruff, mypy strict mode,
pytest, pytest-cov, documentation directories, public-safe example
configuration, a reusable quality gate, a FastAPI application shell, explicit
job domain/API schemas, PostgreSQL persistence scaffolding with Alembic
migrations, an internal repository layer for job persistence/state transitions,
a Redis-backed queue abstraction for job-ID dispatch signals, a job service
layer for create/get/list/cancel workflows, FastAPI job routes for those
workflows, safe allowlisted built-in demo job handlers, a worker CLI/runtime,
retry/dead-letter behaviour, lease-based stale job recovery, and cooperative
worker cancellation handling.

Ticket 012 added:

- A cooperative cancellation hook on `JobHandlerContext` that lets handlers ask
  whether their running job has been moved to `cancel_requested` without giving
  handlers direct database access.
- A bounded polling loop in the safe `sleep` handler so it can observe
  cancellation between short `asyncio.sleep` intervals.
- A repository-owned `mark_cancelled()` transition that moves a worker-owned
  running or `cancel_requested` job to terminal `cancelled`, clears lease fields,
  and records `finished_at`.
- Worker-side cancellation checks before handler execution, after handler
  completion, and before retry/dead-letter recording so cancellation wins over a
  late success/failure when the request has been persisted.
- A distinct `WorkerProcessOutcome.CANCELLED` outcome and structured worker logs
  for cancelled queued dispatch signals and cooperatively cancelled running jobs.
- Tests covering queued cancellation dispatch handling, running `sleep`
  cancellation, handler cancellation polling, and repository cancellation
  ownership checks.
- Documentation updates in the README, handler docs, and runbook.

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

- `uv run pytest tests/test_job_handlers.py tests/test_job_repository.py tests/test_worker_runtime.py -q` — passed (`27 passed`).
- `uv run mypy src tests` — passed.
- `uv run pytest -q` — passed (`68 passed`).

## Public-safety notes

This project is an independent public portfolio project.

Do not add employer code, private data, internal URLs, credentials, screenshots,
non-public architecture, or anything implying employer endorsement.

Do not implement arbitrary shell command execution. Jobs must be safe
allowlisted demo handlers only.

## Latest cycle notes

- Implemented only the worker cancellation behaviour required by ticket 012;
  readiness checks, Prometheus `/metrics`, optional auth, Docker Compose stack,
  and CI were not introduced.
- Preserved public-safety constraints: cancellation only reads and updates
  PostgreSQL job state and acknowledges job UUID dispatch signals; it does not
  run shell commands, subprocesses, containers, user-submitted code, or
  host-level operations.
- Kept cancellation on the intended boundary path: worker runtime -> worker
  service -> handler context/repository/queue -> database/Redis.
- PostgreSQL remains the source of truth. Redis still carries only job UUID
  dispatch signals and may contain stale signals for queued jobs that have
  already been cancelled; workers acknowledge those safely after the database
  claim fails.

## Limitations

Worker cancellation is cooperative. Queued jobs cancel immediately, and running
jobs are marked `cancel_requested` until the worker reaches a cancellation check
or a result-recording boundary. The `sleep` handler observes cancellation between
short intervals; other handlers are fast demo handlers and only observe
cancellation at worker boundaries. Prometheus `/metrics`, `/readyz`, optional
auth, Docker Compose, and CI remain future tickets. Local end-to-end execution
currently requires separately managed PostgreSQL and Redis services because the
Docker Compose stack is not implemented yet.

## Next recommended ticket

Ticket 013.
