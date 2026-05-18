# Runbook

Operational notes will expand as Docker Compose, readiness checks, metrics, and
CI are added. Current local end-to-end runs require separately managed
PostgreSQL and Redis services.

## Retry and dead-letter handling

Workers run only allowlisted built-in demo handlers; they never execute shell
commands, subprocesses, containers, or user-provided code.

Retry policy:

1. A job starts with `attempts = 0` in `queued` state.
2. Claiming a queued job moves it to `running` and increments `attempts` by one.
3. If the handler succeeds, the worker stores the JSON result, clears any prior
   error, clears the lease fields, and marks the job `succeeded`.
4. If the handler fails and `attempts < max_attempts`, the worker stores a safe
   truncated error message, clears the lease fields, requeues the job as
   `queued`, and publishes a new Redis dispatch signal.
5. If the handler fails and `attempts >= max_attempts`, the worker stores the
   safe error message, clears the lease fields, records `finished_at`, and marks
   the job `dead_lettered`.

The `fail_once` handler demonstrates recovery: attempt 1 fails and is requeued;
attempt 2 succeeds. The `always_fail` handler demonstrates dead-lettering after
`max_attempts` is reached.

Error messages are stored as bounded strings with the exception type prefix.
Stack traces are logged by the worker for unexpected exceptions but are not
stored in the job record.

## Cancellation handling

Cancellation is persisted in PostgreSQL; Redis messages remain only dispatch
signals. Cancelling a `queued` job moves it directly to the terminal
`cancelled` state. A later worker that receives the stale dispatch signal will
fail to claim the non-queued row, acknowledge the signal, and log a cancellation
outcome.

Cancelling a `running` job moves it to `cancel_requested` while preserving the
current lease owner. Workers pass a cooperative cancellation check into safe
handlers. The `sleep` handler checks between short bounded `asyncio.sleep`
intervals and raises a safe cancellation error when the request is observed. The
worker then records the terminal `cancelled` state, clears lease fields, records
`finished_at`, acknowledges the dispatch signal, and logs `worker_outcome` as
`cancelled`.

Handlers that finish before noticing a cancellation request are checked again
before success/failure is recorded. If the request is present, cancellation wins
and the worker records `cancelled` instead of retrying or succeeding. Handlers
remain allowlisted demo functions only; cancellation does not introduce shell
commands, subprocesses, containers, user-provided code, or host-level actions.

## Lease and stale job recovery

Workers claim queued jobs by setting `lease_owner` and `lease_expires_at` while
moving the job to `running`. The claim also increments `attempts`, so the running
attempt is counted even if the worker later crashes.

Each worker loop performs an explicit stale recovery pass before polling Redis.
A running job is stale when `lease_expires_at` is in the past:

1. If `attempts < max_attempts`, recovery stores a bounded
   `StaleLeaseRecovery` error message, clears the lease fields, moves the job
   back to `queued`, and publishes a fresh Redis dispatch signal.
2. If `attempts >= max_attempts`, recovery stores the same bounded error style,
   clears the lease fields, records `finished_at`, and marks the job
   `dead_lettered`.

If a slow original worker finishes after another worker has recovered its stale
lease, the repository state check prevents the late worker from overwriting the
newer state. Keep `JOB_RUNNER_JOB_LEASE_SECONDS` comfortably above expected demo
handler runtime to avoid unnecessary duplicate execution.
