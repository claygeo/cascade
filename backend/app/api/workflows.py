"""Workflow CRUD (org-scoped, role-gated). Steps are replaced wholesale on update."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..db import get_session
from ..enums import Role
from ..models import User, Workflow, WorkflowStep
from ..schemas import StepIn, WorkflowCreate, WorkflowOut, WorkflowSummary, WorkflowUpdate
from .deps import get_current_user, get_membership, require_role

router = APIRouter(prefix="/orgs/{org_id}/workflows", tags=["workflows"])


def _validate_steps(steps: list[StepIn]) -> None:
    names = [s.name for s in steps]
    if len(set(names)) != len(names):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "step names must be unique")
    if any(n.isdigit() for n in names):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "step name cannot be purely numeric")


async def _load(session: AsyncSession, org_id: uuid.UUID, workflow_id: uuid.UUID) -> Workflow:
    wf = (
        await session.execute(
            select(Workflow)
            .options(selectinload(Workflow.steps))
            .where(Workflow.id == workflow_id, Workflow.org_id == org_id)
        )
    ).scalar_one_or_none()
    if wf is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "workflow not found")
    return wf


@router.get("", response_model=list[WorkflowSummary])
async def list_workflows(
    org_id: uuid.UUID,
    _m=Depends(get_membership),
    session: AsyncSession = Depends(get_session),
) -> list[WorkflowSummary]:
    rows = (
        await session.execute(
            select(Workflow).where(Workflow.org_id == org_id).order_by(Workflow.updated_at.desc())
        )
    ).scalars().all()
    return [WorkflowSummary.model_validate(w) for w in rows]


@router.post("", response_model=WorkflowOut, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    org_id: uuid.UUID,
    body: WorkflowCreate,
    _m=Depends(require_role(Role.editor)),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> WorkflowOut:
    _validate_steps(body.steps)
    wf = Workflow(org_id=org_id, name=body.name, description=body.description, created_by=user.id)
    session.add(wf)
    await session.flush()
    for i, step in enumerate(body.steps):
        session.add(
            WorkflowStep(workflow_id=wf.id, position=i, type=step.type, name=step.name, config=step.config)
        )
    await session.commit()
    return WorkflowOut.model_validate(await _load(session, org_id, wf.id))


@router.get("/{workflow_id}", response_model=WorkflowOut)
async def get_workflow(
    org_id: uuid.UUID,
    workflow_id: uuid.UUID,
    _m=Depends(get_membership),
    session: AsyncSession = Depends(get_session),
) -> WorkflowOut:
    return WorkflowOut.model_validate(await _load(session, org_id, workflow_id))


@router.put("/{workflow_id}", response_model=WorkflowOut)
async def update_workflow(
    org_id: uuid.UUID,
    workflow_id: uuid.UUID,
    body: WorkflowUpdate,
    _m=Depends(require_role(Role.editor)),
    session: AsyncSession = Depends(get_session),
) -> WorkflowOut:
    wf = await _load(session, org_id, workflow_id)
    if wf.is_sample:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "the sample workflow is read-only")
    if body.name is not None:
        wf.name = body.name
    if body.description is not None:
        wf.description = body.description
    if body.steps is not None:
        _validate_steps(body.steps)
        await session.execute(delete(WorkflowStep).where(WorkflowStep.workflow_id == wf.id))
        for i, step in enumerate(body.steps):
            session.add(
                WorkflowStep(
                    workflow_id=wf.id, position=i, type=step.type, name=step.name, config=step.config
                )
            )
    await session.commit()
    return WorkflowOut.model_validate(await _load(session, org_id, workflow_id))


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    org_id: uuid.UUID,
    workflow_id: uuid.UUID,
    _m=Depends(require_role(Role.editor)),
    session: AsyncSession = Depends(get_session),
):
    wf = await _load(session, org_id, workflow_id)
    if wf.is_sample:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "cannot delete the sample workflow")
    await session.delete(wf)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
