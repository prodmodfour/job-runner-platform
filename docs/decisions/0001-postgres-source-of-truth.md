# 0001 — PostgreSQL as source of truth

## Status

Accepted for the current build stage.

## Context

The platform needs durable, queryable job state for API requests and worker
processing. Job creation, idempotency, attempts, retries, dead-letter handling,
cancellation, leases, timestamps, results, and safe error messages must survive
API restarts, worker crashes, and duplicate or missing Redis dispatch signals.

The project also has strict public-safety constraints. Persisted jobs may refer
only to safe built-in demo handler names and JSON payloads; the system must not
persist or execute arbitrary shell commands, scripts, containers, Python code
strings, or host-level operations.

## Decision

Use PostgreSQL as the authoritative source of truth for jobs and all lifecycle
state transitions.

The `jobs` table stores the durable job record, including:

- UUID primary key;
- allowlisted `job_type` and explicit `status`;
- JSON `payload` and nullable JSON `result`;
- bounded nullable `error_message`;
- `attempts` and `max_attempts`;
- optional `idempotency_key` with a unique partial index;
- optional `lease_owner` and `lease_expires_at`;
- `created_at`, `updated_at`, `queued_at`, `started_at`, and `finished_at`.

All SQL and row-level state transitions live behind the repository layer.
Services coordinate business workflows, routes remain thin HTTP adapters, and
workers must claim a queued job through PostgreSQL before running any handler.
Redis carries job UUID dispatch signals only and never becomes authoritative for
job existence or status.

Schema changes are managed through Alembic migrations so the data model is
explicit and reviewable.

## Consequences

- Jobs remain durable when API processes, workers, or Redis restart.
- Idempotent submission can be enforced with a database uniqueness constraint.
- Duplicate Redis messages are safe because the database row state determines
  whether a worker may run a job.
- Recovery operations can inspect persisted leases and attempts without trusting
  worker-local memory.
- PostgreSQL availability is required for creating, listing, claiming, and
  completing jobs; readiness checks report database availability explicitly.
- The repository layer must keep transactions and state checks disciplined so
  routes and workers do not bypass the source of truth.
- The design is heavier than an in-memory demo queue, but it demonstrates the
  persistence and reliability boundaries expected from a backend/platform job
  system.
