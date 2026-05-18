# 0003 — Allowlisted demo job handlers

## Status

Accepted for the current build stage.

## Context

A portfolio job runner should demonstrate worker execution, retries,
dead-lettering, cancellation, metrics, and logs without becoming a remote command
execution system. Public-safety rules explicitly prohibit arbitrary user
commands, scripts, Docker containers, Python code strings, subprocesses, or
host-level operations.

The project still needs realistic handler behaviour for demos and tests: a
successful payload echo, bounded waiting for cancellation, deterministic checksum
work, one retryable failure, and a repeatable dead-letter path.

## Decision

Run only safe built-in handlers selected from the `JobType` enum and registered
in the in-process handler registry:

- `echo` returns the submitted JSON object;
- `sleep` waits with bounded `asyncio.sleep` intervals and checks cooperative
  cancellation;
- `checksum` computes a SHA-256 digest for provided text;
- `fail_once` fails on the first attempt and succeeds on a later attempt;
- `always_fail` fails safely on every attempt for dead-letter demos.

A job type is a symbolic handler name, not a shell command, script path,
container image, or code snippet. API schemas, domain definitions, database
constraints, and handler lookup all restrict execution to this allowlist.
Handler payloads must be JSON objects and are validated with Pydantic models
where a handler needs a specific shape. Demo limits bound sleep duration and
checksum input size.

Adding a new handler requires an intentional code change, tests, documentation,
and any needed schema or migration updates.

## Consequences

- The worker demonstrates meaningful execution paths while remaining safe for a
  public portfolio repository.
- Tests can cover success, retry, dead-letter, invalid payload, and cancellation
  behaviour deterministically.
- The system is not a general-purpose task executor and intentionally rejects
  unsafe or unknown job types.
- Users cannot extend execution by submitting command strings or code through the
  API; extension happens only through reviewed source changes.
- Handler limits keep local demos predictable, but production-specific long
  running workloads would require a different reviewed handler model and lease
  strategy.
