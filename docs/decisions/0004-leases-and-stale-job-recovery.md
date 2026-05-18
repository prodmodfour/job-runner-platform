# 0004 — Leases and stale job recovery

## Status

Accepted for the current build stage.

## Context

PostgreSQL is the source of truth for job state, while Redis carries only job ID
wake-up signals. A worker can crash, be terminated, or lose connectivity after
claiming a job. Without a lease, that job could remain `running` forever even
though no worker is still making progress.

The platform must keep recovery public-safe: recovery may only update persisted
job state and publish job ID dispatch signals. It must not execute shell
commands, subprocesses, containers, user-provided code, or host-level actions.

## Decision

A worker claim records both `lease_owner` and `lease_expires_at` on the job row
and increments `attempts` once for that handler execution attempt.

Stale recovery is an explicit worker-service operation. On each worker loop pass,
the runtime asks the service to recover `running` jobs whose `lease_expires_at` is
in the past. Recovery applies the same attempt policy used by handler failures:

- if `attempts < max_attempts`, the job is requeued, lease fields are cleared, a
  bounded `StaleLeaseRecovery` error message is stored, and a fresh Redis
  dispatch signal is published after the database transaction commits;
- if `attempts >= max_attempts`, the job is moved to `dead_lettered`, lease
  fields are cleared, `finished_at` is recorded, and no Redis signal is
  published.

Duplicate or racing recovery attempts are safe because state transitions still go
through repository methods that lock and check the PostgreSQL row before
updating it.

## Consequences

- A crashed worker does not permanently strand a `running` job.
- The attempt consumed by the stale execution is preserved; recovery does not
  hide failed or abandoned work.
- Redis remains a dispatch signal only. PostgreSQL decides whether a recovered
  job can run again.
- A very short lease can cause duplicate execution if an original worker is slow
  but still alive. Demo handlers are therefore designed to be safe and bounded,
  and production deployments should choose a lease duration longer than expected
  handler runtime.
- Lease extension/heartbeats are intentionally not part of this build stage; the
  current model relies on bounded demo handlers and explicit stale recovery.
