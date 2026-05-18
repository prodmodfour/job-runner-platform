from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi import status as http_status

from job_runner_platform.api.dependencies import JobServiceDependency
from job_runner_platform.api.schemas import (
    CancellationResponse,
    CreateJobRequest,
    CreateJobResponse,
    JobDetailResponse,
    JobListResponse,
)
from job_runner_platform.domain.jobs import JobStatus
from job_runner_platform.services import (
    DEFAULT_LIST_LIMIT,
    MAX_LIST_LIMIT,
    InvalidJobStatusError,
    InvalidJobTypeError,
    InvalidPaginationError,
    JobCancellationConflictError,
    JobNotFoundError,
)

router = APIRouter(tags=["jobs"])


@router.post(
    "/jobs",
    response_model=CreateJobResponse,
    status_code=http_status.HTTP_201_CREATED,
)
async def create_job(
    body: CreateJobRequest,
    response: Response,
    service: JobServiceDependency,
) -> CreateJobResponse:
    """Submit a safe allowlisted demo job for asynchronous execution."""

    try:
        result = await service.create_job(
            job_type=body.job_type,
            payload=body.payload,
            priority=body.priority,
            max_attempts=body.max_attempts,
            idempotency_key=body.idempotency_key,
        )
    except InvalidJobTypeError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    if result.idempotency_replayed:
        response.status_code = http_status.HTTP_200_OK

    return CreateJobResponse(
        job=_job_detail_response(result.job),
        idempotency_replayed=result.idempotency_replayed,
    )


@router.get("/jobs", response_model=JobListResponse)
async def list_jobs(
    service: JobServiceDependency,
    limit: Annotated[int, Query(ge=1, le=MAX_LIST_LIMIT)] = DEFAULT_LIST_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
    status: Annotated[JobStatus | None, Query(alias="status")] = None,
) -> JobListResponse:
    """List jobs with bounded pagination and an optional status filter."""

    try:
        result = await service.list_jobs(limit=limit, offset=offset, status=status)
    except (InvalidJobStatusError, InvalidPaginationError) as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return JobListResponse(
        items=[_job_detail_response(job) for job in result.items],
        count=result.count,
        limit=result.limit,
        offset=result.offset,
    )


@router.get("/jobs/{job_id}", response_model=JobDetailResponse)
async def get_job(
    job_id: UUID,
    service: JobServiceDependency,
) -> JobDetailResponse:
    """Fetch one job by its UUID."""

    job = await service.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"job {job_id} was not found",
        )
    return _job_detail_response(job)


@router.post("/jobs/{job_id}/cancel", response_model=CancellationResponse)
async def cancel_job(
    job_id: UUID,
    service: JobServiceDependency,
) -> CancellationResponse:
    """Cancel a queued job or request cooperative cancellation for a running job."""

    try:
        result = await service.cancel_job(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except JobCancellationConflictError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return CancellationResponse(
        job=_job_detail_response(result.job),
        cancellation_requested=result.cancellation_requested,
        message=result.message,
    )


def _job_detail_response(job: object) -> JobDetailResponse:
    return JobDetailResponse.model_validate(job, from_attributes=True)
