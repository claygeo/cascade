"""Run endpoints: enqueue a run (the worker executes it) and read run state.

Enqueuing just inserts a ``queued`` row — the background worker claims and
executes it. The frontend polls ``GET /runs/{id}`` to stream live step status.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..config import settings
from ..db import get_session
from ..enums import Role, RunStatus, RunTrigger
from ..models import ProviderKey, Run, User, Workflow
from ..schemas import RunCreate, RunOut, RunSummary
from .deps import get_current_user, get_membership, require_role

router = APIRouter(prefix="/orgs/{org_id}", tags=["runs"])


@router.post(
    "/workflows/{workflow_id}/runs",
    response_model=RunSummary,
    status_code=status.HTTP_202_ACCEPTED,
)
async def enqueue_run(
    org_id: uuid.UUID,
    workflow_id: uuid.UUID,
    body: RunCreate,
    _m=Depends(require_role(Role.editor)),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> RunSummary:
    wf = (
        await session.execute(
            select(Workflow).where(Workflow.id == workflow_id, Workflow.org_id == org_id)
        )
    ).scalar_one_or_none()
    if wf is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "workflow not found")

    if body.provider_key_id is not None:
        owns_key = (
            await session.execute(
                select(ProviderKey.id).where(
                    ProviderKey.id == body.provider_key_id, ProviderKey.org_id == org_id
                )
            )
        ).first()
        if owns_key is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "provider key not found")

    run = Run(
        workflow_id=wf.id,
        org_id=org_id,
        status=RunStatus.queued,
        trigger=RunTrigger.manual,
        input=body.input,
        provider_key_id=body.provider_key_id,
        created_by=user.id,
        max_attempts=settings.run_max_attempts,
    )
    session.add(run)
    await session.commit()
    return RunSummary.model_validate(run)


@router.get("/runs", response_model=list[RunSummary])
async def list_runs(
    org_id: uuid.UUID,
    _m=Depends(get_membership),
    session: AsyncSession = Depends(get_session),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[RunSummary]:
    rows = (
        await session.execute(
            select(Run).where(Run.org_id == org_id).order_by(Run.created_at.desc()).limit(limit)
        )
    ).scalars().all()
    return [RunSummary.model_validate(r) for r in rows]


@router.get("/runs/{run_id}", response_model=RunOut)
async def get_run(
    org_id: uuid.UUID,
    run_id: uuid.UUID,
    _m=Depends(get_membership),
    session: AsyncSession = Depends(get_session),
) -> RunOut:
    run = (
        await session.execute(
            select(Run).options(selectinload(Run.step_runs)).where(
                Run.id == run_id, Run.org_id == org_id
            )
        )
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")
    return RunOut.model_validate(run)
