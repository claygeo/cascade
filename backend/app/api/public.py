"""Public, no-auth endpoints powering the landing-page "try it" demo.

A visitor can run the seeded sample workflow once (rate-limited per IP) on the
server's shared OpenRouter key, and poll its live progress — no signup needed.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..config import settings
from ..db import get_session
from ..enums import RunStatus, RunTrigger
from ..models import Run, Workflow
from ..schemas import RunOut, RunSummary, SampleRunRequest
from ..services.rate_limit import SlidingWindowLimiter

router = APIRouter(prefix="/public", tags=["public"])

_limiter = SlidingWindowLimiter(
    max_events=settings.sample_runs_per_hour_per_ip, per_seconds=3600.0
)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _sample_workflow(session: AsyncSession) -> Workflow:
    wf = (
        await session.execute(
            select(Workflow)
            .options(selectinload(Workflow.steps))
            .where(Workflow.is_sample.is_(True))
            .order_by(Workflow.created_at)
            .limit(1)
        )
    ).scalar_one_or_none()
    if wf is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "sample workflow not seeded yet")
    return wf


@router.get("/sample", response_model=dict)
async def get_sample(session: AsyncSession = Depends(get_session)) -> dict:
    wf = await _sample_workflow(session)
    return {
        "id": str(wf.id),
        "name": wf.name,
        "description": wf.description,
        "steps": [
            {"position": s.position, "type": s.type, "name": s.name, "config": s.config}
            for s in wf.steps
        ],
    }


@router.post("/sample/runs", response_model=RunSummary, status_code=status.HTTP_202_ACCEPTED)
async def run_sample(
    request: Request,
    body: SampleRunRequest,
    session: AsyncSession = Depends(get_session),
) -> RunSummary:
    allowed, retry_after = _limiter.check(_client_ip(request))
    if not allowed:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"sample rate limit reached; retry in ~{retry_after}s",
            headers={"Retry-After": str(retry_after)},
        )
    wf = await _sample_workflow(session)
    # The sample references {{ input.tone }}; default it so an empty body still works.
    run_input = {"tone": "witty", **(body.input or {})}
    run = Run(
        workflow_id=wf.id,
        org_id=wf.org_id,
        status=RunStatus.queued,
        trigger=RunTrigger.sample,
        input=run_input,
        provider_key_id=None,  # uses the server's shared key
        max_attempts=settings.run_max_attempts,
    )
    session.add(run)
    await session.commit()
    return RunSummary.model_validate(run)


@router.get("/runs/{run_id}", response_model=RunOut)
async def get_sample_run(
    run_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> RunOut:
    run = (
        await session.execute(
            select(Run)
            .options(selectinload(Run.step_runs))
            .where(Run.id == run_id, Run.trigger == RunTrigger.sample)
        )
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")
    return RunOut.model_validate(run)
