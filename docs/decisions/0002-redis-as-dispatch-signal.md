# 0002 — Redis as dispatch signal

## Status

Accepted for the current build stage.

## Context

PostgreSQL is the durable source of truth for jobs, state transitions, attempts,
leases, idempotency keys, results, and errors. Workers still need a low-latency
way to notice newly queued jobs without polling PostgreSQL aggressively.

The queue layer must hide Redis details from services and workers, tolerate
duplicate messages, and remain public-safe. It must never execute user-provided
commands, scripts, containers, or code strings; queue messages are job UUIDs
only.

## Decision

Use Redis only as a dispatch-signal transport for persisted job IDs.

The queue abstraction exposes:

- `enqueue(job_id)` to publish a job UUID signal after a job row exists.
- `dequeue(timeout_seconds=...)` to poll the next job UUID signal.
- `acknowledge(job_id)` so callers have an explicit completion hook.
- `is_ready()` for dependency/readiness checks.

The Redis implementation uses one Redis list key with `LPUSH` for enqueue and
`RPOP`/`BRPOP` for dequeue. This keeps the design simple and FIFO for normal
operation. Redis list messages are removed when popped, so acknowledgement is a
no-op. Duplicate Redis signals are allowed: a worker or service must claim the
job through PostgreSQL before running it, and a duplicate claim is ignored when
the row is already running, terminal, cancelled, or otherwise not queued.

An in-memory queue implementation is available for tests and follows the same
semantics, including allowing duplicate job IDs.

## Consequences

- Redis remains an optimization for dispatch latency, not the authority for job
  existence or state.
- Duplicate messages are safe because PostgreSQL state checks gate execution.
- The queue abstraction keeps routes and future services/workers free of direct
  Redis calls.
- A popped Redis signal can be lost if a process crashes before claiming the
  database row. The queued PostgreSQL row remains durable; future worker/recovery
  logic should reconcile queued or stale rows by re-signalling or scanning the
  source of truth as later tickets add worker runtime and lease recovery.
- The design can evolve to Redis Streams later if true in-flight acknowledgement
  becomes necessary, without changing route or repository boundaries.
