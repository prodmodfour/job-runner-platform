from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from job_runner_platform.database.base import Base
from job_runner_platform.domain.jobs import (
    DEFAULT_JOB_PRIORITY,
    DEFAULT_MAX_ATTEMPTS,
    JobStatus,
    JobType,
)

JOB_TYPE_VALUES = tuple(job_type.value for job_type in JobType)
JOB_STATUS_VALUES = tuple(status.value for status in JobStatus)


def utc_now() -> datetime:
    """Return an aware UTC timestamp for application-side defaults."""

    return datetime.now(UTC)


def sql_literal_tuple(values: tuple[str, ...]) -> str:
    """Render a small static string tuple for SQL check constraints."""

    quoted_values = ", ".join(f"'{value}'" for value in values)
    return f"({quoted_values})"


class JobModel(Base):
    """Persistent job record stored in PostgreSQL."""

    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            f"job_type IN {sql_literal_tuple(JOB_TYPE_VALUES)}",
            name="ck_jobs_job_type_allowed",
        ),
        CheckConstraint(
            f"status IN {sql_literal_tuple(JOB_STATUS_VALUES)}",
            name="ck_jobs_status_allowed",
        ),
        CheckConstraint("attempts >= 0", name="ck_jobs_attempts_non_negative"),
        CheckConstraint("max_attempts >= 1", name="ck_jobs_max_attempts_positive"),
        CheckConstraint(
            "priority >= -100 AND priority <= 100",
            name="ck_jobs_priority_range",
        ),
        Index("ix_jobs_status", "status"),
        Index("ix_jobs_created_at", "created_at"),
        Index(
            "uq_jobs_idempotency_key",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
        Index(
            "ix_jobs_lease_expires_at",
            "lease_expires_at",
            postgresql_where=text("lease_expires_at IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    job_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=JobStatus.QUEUED.value,
        server_default=JobStatus.QUEUED.value,
    )
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=DEFAULT_JOB_PRIORITY,
        server_default=str(DEFAULT_JOB_PRIORITY),
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=DEFAULT_MAX_ATTEMPTS,
        server_default=str(DEFAULT_MAX_ATTEMPTS),
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )
    queued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
