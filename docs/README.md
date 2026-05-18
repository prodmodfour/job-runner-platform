# Documentation

Project documentation lives here. These docs describe the current public-safe portfolio implementation and link to narrower references where useful.

- [Architecture](architecture.md) — code boundaries, job lifecycle, state transitions, queue design, retries, cancellation, leases, metrics, and limitations.
- [API walkthrough](api-walkthrough.md) — local HTTP examples, response shapes, idempotency, auth behaviour, and error responses.
- [Local smoke demo](demo-smoke.md) — script-driven Compose walkthrough for echo, checksum, retry, dead-letter, cancellation, and metrics checks.
- [Operations](operations.md) — local Docker Compose operation, manual runs, configuration, migrations, readiness, observability, and failure modes.
- [Runbook](runbook.md) — practical triage procedures for health, readiness, queued jobs, retries, dead-letter, cancellation, stale leases, metrics, auth, and quality gates.
- [Safe built-in job handlers](job-handlers.md) — allowlisted handler payloads, results, and limits.
- [Local observability](observability.md) — Prometheus and Grafana local scrape/dashboard notes.
- [Architecture decision records](decisions/README.md) — accepted design records for implemented reliability choices.
