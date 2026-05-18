# Safe built-in job handlers

Job execution is limited to these public-safe built-in demo handlers. Handler names are identifiers, not shell commands, scripts, containers, subprocesses, or user-provided code. Payloads must be JSON objects.

| Handler | Payload shape | Result shape | Notes |
| --- | --- | --- | --- |
| `echo` | Any JSON object. Example: `{ "message": "hello" }` | `{ "payload": { ... } }` | Returns a JSON copy of the submitted payload. |
| `sleep` | `{ "seconds": 0.5 }` where `seconds` is a number from `0` through `5.0`. | `{ "slept_seconds": 0.5 }` | Uses `asyncio.sleep`; no subprocesses or host operations. |
| `checksum` | `{ "text": "hello", "algorithm": "sha256" }`; `algorithm` is optional and currently only `sha256`; text is capped at 1,000,000 UTF-8 bytes. | `{ "algorithm": "sha256", "encoding": "utf-8", "checksum": "...", "byte_length": 5 }` | Computes SHA-256 over the supplied UTF-8 text; it never reads files. |
| `fail_once` | `{}` | First attempt raises a safe handler error; later attempts return `{ "failed_once": true, "attempt": 2 }`. | Supports future retry demonstrations without external side effects. |
| `always_fail` | `{}` | Always raises a safe handler error. | Supports future dead-letter demonstrations without external side effects. |

The handler registry is tested to cover exactly the domain allowlist: `echo`, `sleep`, `checksum`, `fail_once`, and `always_fail`.
