# BUILD_NOTES.md

## Current state

Tickets 000 through 008 are complete. The repository now has the initial Python 3.12 `src/` package skeleton, uv/hatchling packaging, Ruff, mypy strict mode, pytest, pytest-cov, documentation directories, public-safe example configuration, a reusable quality gate, a FastAPI application shell, explicit job domain/API schemas, PostgreSQL persistence scaffolding with Alembic migrations, an internal repository layer for job persistence/state transitions, a Redis-backed queue abstraction for job-ID dispatch signals, a job service layer for create/get/list/cancel workflows, FastAPI job routes for those workflows, and safe allowlisted built-in demo job handlers.

Ticket 008 added:

- A `job_runner_platform.handlers` package with an async handler registry for exactly the allowlisted job types: `echo`, `sleep`, `checksum`, `fail_once`, and `always_fail`.
- Safe handler payload validation, JSON-serializable payload checks, a bounded `sleep` duration, SHA-256 checksum handling over supplied UTF-8 text only, and deterministic demo failure handlers for future retry/dead-letter work.
- Handler execution/context error types for future worker integration without introducing a worker runtime in this ticket.
- Unit tests covering each handler, registry coverage, bounded sleep validation, fail-once behaviour, always-fail behaviour, unknown handler rejection, non-JSON payload rejection, and context attempt validation.
- Handler payload/result documentation in `docs/job-handlers.md`, linked from `docs/README.md` and summarized in `README.md`.

## Quality gates

Latest run:

- `scripts/quality-gate.sh` — passed
  - shell syntax checks
  - `uv sync --locked --all-groups`
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run mypy src tests`
  - `uv run pytest --cov=job_runner_platform --cov-report=term-missing`

Additional validation this cycle:

- `uv run ruff check .` — passed after formatting fixes.
- `uv run ruff format --check .` — passed.
- `uv run mypy src tests` — passed.
- `uv run pytest -q` — passed (`56 passed`).

## Public-safety notes

This project is an independent public portfolio project.

Do not add employer code, private data, internal URLs, credentials, screenshots, non-public architecture, or anything implying employer endorsement.

Do not implement arbitrary shell command execution. Jobs must be safe allowlisted demo handlers only.

## Latest cycle notes

- Implemented only the safe allowlisted job handlers required by ticket 008; no worker runtime, retry/dead-letter policy, lease recovery, metrics, auth, Docker Compose stack, or CI were introduced.
- Preserved public-safety constraints: handlers do not run shell commands, subprocesses, containers, user-supplied code, or host filesystem operations.
- Kept handlers isolated and testable so the future worker can call them after claiming jobs through the repository/service boundary.
- Documented handler payload shapes and limits without creating the future ADR/runbook tickets early.

## Limitations

Safe handlers are implemented and unit-tested, but no worker process exists yet to dequeue, claim, execute, and record job results. The API exposes `/jobs` routes and `/healthz`, but `/readyz`, `/metrics`, worker runtime, retry/dead-letter orchestration, cancellation checks inside handlers/workers, auth, Docker Compose, and CI remain future tickets. Local end-to-end job execution still requires future worker and runtime tickets.

## Next recommended ticket

Ticket 009.
