from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Final, cast

from sqlalchemy import JSON, CheckConstraint, Table
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.schema import CreateIndex, CreateTable

from job_runner_platform.database.base import Base
from job_runner_platform.database.models import JobModel
from job_runner_platform.database.session import (
    build_async_engine,
    build_async_sessionmaker,
)
from job_runner_platform.settings import Settings

REQUIRED_JOB_COLUMNS: Final[set[str]] = {
    "id",
    "job_type",
    "status",
    "priority",
    "payload",
    "result",
    "error_message",
    "attempts",
    "max_attempts",
    "idempotency_key",
    "lease_owner",
    "lease_expires_at",
    "created_at",
    "updated_at",
    "queued_at",
    "started_at",
    "finished_at",
}


def test_jobs_table_metadata_defines_required_columns_and_constraints() -> None:
    table = _jobs_table()

    assert table.name == "jobs"
    assert JobModel.metadata is Base.metadata
    assert set(table.c.keys()) == REQUIRED_JOB_COLUMNS
    assert table.c.id.primary_key is True
    assert isinstance(table.c.payload.type, JSON)
    assert isinstance(table.c.result.type, JSON)

    required_non_nullable_columns = {
        "id",
        "job_type",
        "status",
        "priority",
        "payload",
        "attempts",
        "max_attempts",
        "created_at",
        "updated_at",
        "queued_at",
    }
    for column_name in required_non_nullable_columns:
        assert table.c[column_name].nullable is False

    constraint_names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert "ck_jobs_job_type_allowed" in constraint_names
    assert "ck_jobs_status_allowed" in constraint_names
    assert "ck_jobs_attempts_non_negative" in constraint_names
    assert "ck_jobs_max_attempts_positive" in constraint_names
    assert "ck_jobs_priority_range" in constraint_names


def test_jobs_table_metadata_defines_required_indexes() -> None:
    indexes = {
        str(index.name): index
        for index in _jobs_table().indexes
        if index.name is not None
    }

    assert "ix_jobs_status" in indexes
    assert "ix_jobs_created_at" in indexes
    assert "uq_jobs_idempotency_key" in indexes
    assert indexes["uq_jobs_idempotency_key"].unique is True
    assert "ix_jobs_lease_expires_at" in indexes

    idempotency_where = indexes["uq_jobs_idempotency_key"].dialect_options[
        "postgresql"
    ]["where"]
    lease_where = indexes["ix_jobs_lease_expires_at"].dialect_options["postgresql"][
        "where"
    ]
    assert str(idempotency_where) == "idempotency_key IS NOT NULL"
    assert str(lease_where) == "lease_expires_at IS NOT NULL"


def test_jobs_table_ddl_compiles_for_postgresql() -> None:
    dialect = postgresql.dialect()  # type: ignore[no-untyped-call]
    table = _jobs_table()

    table_ddl = str(CreateTable(table).compile(dialect=dialect))
    index_ddl = "\n".join(
        str(CreateIndex(index).compile(dialect=dialect)) for index in table.indexes
    )

    assert "CREATE TABLE jobs" in table_ddl
    assert "id UUID NOT NULL" in table_ddl
    assert "payload JSON NOT NULL" in table_ddl
    assert "TIMESTAMP WITH TIME ZONE" in table_ddl
    assert "CONSTRAINT ck_jobs_status_allowed" in table_ddl
    assert "CREATE INDEX ix_jobs_status ON jobs (status)" in index_ddl
    assert "CREATE INDEX ix_jobs_created_at ON jobs (created_at)" in index_ddl
    assert (
        "CREATE UNIQUE INDEX uq_jobs_idempotency_key ON jobs "
        "(idempotency_key) WHERE idempotency_key IS NOT NULL"
    ) in index_ddl
    assert (
        "CREATE INDEX ix_jobs_lease_expires_at ON jobs "
        "(lease_expires_at) WHERE lease_expires_at IS NOT NULL"
    ) in index_ddl


def test_build_async_engine_and_sessionmaker_use_database_settings() -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://localhost:5432/job_runner_test"
    )
    engine = build_async_engine(settings)

    try:
        assert str(engine.url) == settings.database_url
        session_factory = build_async_sessionmaker(engine)
        asyncio.run(_assert_session_factory_configuration(session_factory))
    finally:
        asyncio.run(engine.dispose())


def test_alembic_configuration_and_initial_revision_exist() -> None:
    assert Path("alembic.ini").is_file()
    assert Path("migrations/env.py").is_file()

    migration = Path("migrations/versions/0001_create_jobs_table.py")
    migration_text = migration.read_text(encoding="utf-8")

    assert migration.is_file()
    assert 'revision: str = "0001_create_jobs_table"' in migration_text
    assert 'op.create_table(\n        "jobs"' in migration_text
    assert 'op.create_index("ix_jobs_status", "jobs", ["status"])' in migration_text


def _jobs_table() -> Table:
    return cast(Table, JobModel.__table__)


async def _assert_session_factory_configuration(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        assert isinstance(session, AsyncSession)
        assert session.sync_session.expire_on_commit is False
        assert session.sync_session.autoflush is False
