from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"
DECISIONS_DIR = DOCS_DIR / "decisions"
REQUIRED_TICKET_020_DOCS = (
    "architecture.md",
    "api-walkthrough.md",
    "operations.md",
    "runbook.md",
)
REQUIRED_ADRS = (
    "0001-postgres-source-of-truth.md",
    "0002-redis-as-dispatch-signal.md",
    "0003-allowlisted-demo-job-handlers.md",
    "0004-leases-and-stale-job-recovery.md",
)
REQUIRED_ADR_SECTIONS = (
    "## Status",
    "## Context",
    "## Decision",
    "## Consequences",
)
REQUIRED_TOPICS = (
    "architecture",
    "job lifecycle",
    "state transitions",
    "queue design",
    "retry",
    "dead-letter",
    "cancellation",
    "leases",
    "metrics",
    "local operation",
    "failure modes",
    "known limitations",
    "postgresql",
    "redis",
    "x-request-id",
    "idempotency",
)


def _read_doc(filename: str) -> str:
    return (DOCS_DIR / filename).read_text(encoding="utf-8")


def test_ticket_020_documentation_files_exist() -> None:
    for filename in REQUIRED_TICKET_020_DOCS:
        assert (DOCS_DIR / filename).is_file(), f"missing docs/{filename}"


def test_ticket_020_documentation_covers_required_topics() -> None:
    corpus = "\n".join(
        _read_doc(filename).casefold() for filename in REQUIRED_TICKET_020_DOCS
    )

    for topic in REQUIRED_TOPICS:
        assert topic in corpus, f"documentation does not cover {topic!r}"


def test_documentation_index_links_ticket_020_docs() -> None:
    index = _read_doc("README.md")

    for filename in REQUIRED_TICKET_020_DOCS:
        assert f"({filename})" in index


def test_architecture_decision_records_exist_and_use_required_sections() -> None:
    for filename in REQUIRED_ADRS:
        path = DECISIONS_DIR / filename
        assert path.is_file(), f"missing docs/decisions/{filename}"
        text = path.read_text(encoding="utf-8")

        for section in REQUIRED_ADR_SECTIONS:
            assert section in text, f"{filename} is missing {section!r}"


def test_decision_index_links_required_adrs() -> None:
    index = (DECISIONS_DIR / "README.md").read_text(encoding="utf-8")

    for filename in REQUIRED_ADRS:
        assert f"({filename})" in index
