from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from job_runner_platform.database.session import (
    build_async_engine,
    build_async_sessionmaker,
    session_scope,
)
from job_runner_platform.queues import JobQueue, RedisJobQueue
from job_runner_platform.repositories import JobRepository
from job_runner_platform.services import JobService
from job_runner_platform.settings import Settings


def get_request_settings(request: Request) -> Settings:
    """Return application settings attached by the app factory."""

    return cast(Settings, request.app.state.settings)


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    """Return the app-scoped async SQLAlchemy session factory.

    The factory and engine are built lazily so liveness checks and tests that
    override the job service do not open database resources.
    """

    existing_factory = getattr(request.app.state, "session_factory", None)
    if existing_factory is not None:
        return cast(async_sessionmaker[AsyncSession], existing_factory)

    settings = get_request_settings(request)
    engine = build_async_engine(settings)
    session_factory = build_async_sessionmaker(engine)
    request.app.state.database_engine = engine
    request.app.state.session_factory = session_factory
    return session_factory


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Provide one transactional SQLAlchemy session per request."""

    session_factory = get_session_factory(request)
    async with session_scope(session_factory) as session:
        yield session


def get_job_queue(request: Request) -> JobQueue:
    """Return the app-scoped Redis dispatch-signal queue."""

    existing_queue = getattr(request.app.state, "job_queue", None)
    if existing_queue is not None:
        return cast(JobQueue, existing_queue)

    settings = get_request_settings(request)
    queue = RedisJobQueue.from_settings(settings)
    request.app.state.job_queue = queue
    return queue


SessionDependency = Annotated[AsyncSession, Depends(get_session, scope="function")]
QueueDependency = Annotated[JobQueue, Depends(get_job_queue)]


async def get_job_service(
    session: SessionDependency,
    queue: QueueDependency,
) -> JobService:
    """Build the job business service for API route handlers."""

    repository = JobRepository(session)
    return JobService(repository=repository, queue=queue)


JobServiceDependency = Annotated[JobService, Depends(get_job_service)]
