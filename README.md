# Job Runner Platform

`job-runner-platform` is an independent public portfolio project that demonstrates backend and platform engineering through a production-style background job platform.

The repository is intentionally public-safe: it uses only generic local configuration, fake demo data, and documented constraints. It is not affiliated with any employer or private system.

## Current status

This first build ticket bootstraps the repository structure, Python packaging, quality tooling, and a basic import test. The FastAPI API, PostgreSQL persistence, Redis dispatch, worker runtime, retries, cancellation, leases, metrics, Docker Compose, and CI will be added in later tickets.

## Public-safety constraints

This project must not include employer code, private data, internal URLs or hostnames, credentials, tokens, screenshots of private systems, non-public architecture, or anything implying employer endorsement.

The platform must not implement arbitrary shell command execution. Future jobs are limited to safe allowlisted demo handlers such as `echo`, `sleep`, `checksum`, `fail_once`, and `always_fail`.

## Backend/platform skills demonstrated

The completed project is intended to demonstrate:

- FastAPI backend API design
- PostgreSQL persistence and migrations
- Redis-backed queue/dispatch signalling
- Worker process design
- retries, dead-letter handling, idempotency, cancellation, and leases
- structured JSON logging and request ID propagation
- Prometheus metrics and health/readiness checks
- Docker Compose local operations
- GitHub Actions CI, tests, docs, runbooks, and architecture decisions

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Make (optional convenience wrapper)

## Development quick start

```bash
uv sync --all-groups
uv run pytest
scripts/quality-gate.sh
```

Or use Make:

```bash
make quality
```

## Repository layout

```text
src/job_runner_platform/   Python package source
tests/                     pytest test suite
docs/                      project documentation
docs/decisions/            architecture decision records
scripts/                   local automation and quality gates
```

## Configuration

Runtime configuration will use environment variables prefixed with `JOB_RUNNER_`. See `example.env` for public-safe local placeholders.

## Quality gate

`scripts/quality-gate.sh` currently runs:

- shell syntax checks for repository scripts
- `uv sync`
- Ruff lint checks
- Ruff format checks
- mypy in strict mode
- pytest with coverage
