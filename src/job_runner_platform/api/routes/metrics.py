from __future__ import annotations

from fastapi import APIRouter, Response

from job_runner_platform.observability import METRICS_CONTENT_TYPE, render_metrics

router = APIRouter(tags=["system"])


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    """Return Prometheus metrics for API and job lifecycle instrumentation."""

    return Response(content=render_metrics(), media_type=METRICS_CONTENT_TYPE)
