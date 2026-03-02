"""Background job routes.

Endpoints:
  GET /v1/jobs/{job_id} — Check status of a background job
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from reinforce_spec.server.schemas import JobResponse

router = APIRouter(tags=["jobs"])


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job_status(job_id: str, request: Request) -> JobResponse:
    """Look up the status of a background job.

    Returns 404 if the job ID is unknown.
    """
    queue = getattr(request.app.state, "job_queue", None)
    if queue is None:
        raise HTTPException(status_code=501, detail="Job queue not configured")

    job = queue.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")

    return JobResponse(
        job_id=job.id,
        name=job.name,
        status=job.status.value,
        created_at=job.created_at.isoformat(),
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        error=job.error,
    )
