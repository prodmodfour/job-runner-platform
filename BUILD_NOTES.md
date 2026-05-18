# BUILD_NOTES.md

## Current state

Tickets 000, 001, 002, 003, 004, and 005 are complete. The repository now has the initial Python 3.12 `src/` package skeleton, uv/hatchling packaging, Ruff, mypy strict mode, pytest, pytest-cov, documentation directories, public-safe example configuration, a reusable quality gate, a FastAPI application shell, explicit job domain/API schemas, PostgreSQL persistence scaffolding with Alembic migrations, an internal repository layer for job persistence/state transitions, and a Redis-backed queue abstraction for job-ID dispatch signals.

Ticket 005 added:

- `job_runner_platform.queues.JobQueue`, a narrow async protocol for enqueue, dequeue/poll, acknowledgement, and readiness checks.
- `RedisJobQueue`, backed by a Redis list using `LPUSH` plus `RPOP`/`BRPOP` so Redis remains a dispatch signal instead of the source of truth.
- `InMemoryJobQueue`, a test fake with the same duplicate-message semantics and configurable readiness.
- `JOB_RUNNER_REDIS_URL` settings support and a runtime dependency on `redis`.
- Tests for queue enqueue/dequeue/acknowledgement/readiness behaviour and duplicate dispatch signals being safely ignored by database claim state.
- `docs/decisions/0002-redis-as-dispatch-signal.md` documenting the Redis-as-signal design, duplicate tolerance, and limitations.
- README updates for Redis configuration and queue architecture.

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

- `uv run ruff check .` — passed.
- `uv run ruff format --check .` — passed.
- `uv run mypy src tests` — passed.
- `uv run pytest -q` — passed.

## Public-safety notes

This project is an independent public portfolio project.

Do not add employer code, private data, internal URLs, credentials, screenshots, non-public architecture, or anything implying employer endorsement.

Do not implement arbitrary shell command execution. Jobs must be safe allowlisted demo handlers only.

## Latest cycle notes

- Added only the queue abstraction required by ticket 005; no service layer, job routes, worker runtime, handler execution, readiness endpoint, metrics, retries, or Docker Compose stack were introduced.
- Kept Redis calls hidden behind the queue package so future routes can remain thin and future services/workers do not depend on Redis client details.
- Chose a simple Redis list design because PostgreSQL remains the durable job state authority; duplicate Redis messages are permitted and database claim checks prevent duplicate execution.
- No arbitrary command execution, subprocess execution, credentials, private details, or employer-specific content were added.

## Limitations

The API shell still exposes only `/healthz`; `/readyz`, `/metrics`, job routes, service methods, worker runtime, auth, Docker Compose, and CI remain future tickets. Queue tests use fakes and SQLite-backed repository checks so the quality gate remains self-contained before Docker Compose exists. The Redis list signal can be lost if a process crashes after popping but before claiming a job; the durable PostgreSQL row remains queued, and future worker/recovery tickets should reconcile queued or stale rows from the source of truth.

## Next recommended ticket

Ticket 006.
