from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"
REQUIRED_TICKET_020_DOCS = (
    "architecture.md",
    "api-walkthrough.md",
    "operations.md",
    "runbook.md",
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
