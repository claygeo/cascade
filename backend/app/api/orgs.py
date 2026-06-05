"""Organization membership management (the permissions surface).

Only owners can add/remove members or change roles. The last owner can't be
removed or demoted — that would orphan the org.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..enums import Role
from ..models import Membership, User
from ..schemas import AddMemberRequest, MemberOut
from .deps import get_membership, require_role

router = APIRouter(prefix="/orgs/{org_id}/members", tags=["members"])


class UpdateRoleRequest(BaseModel):
    role: Role


async def _owner_count(session: AsyncSession, org_id: uuid.UUID) -> int:
    rows = (
        await session.execute(
            select(Membership.id).where(Membership.org_id == org_id, Membership.role == Role.owner)
        )
    ).all()
    return len(rows)


@router.get("", response_model=list[MemberOut])
async def list_members(
    org_id: uuid.UUID,
    _m=Depends(get_membership),
    session: AsyncSession = Depends(get_session),
) -> list[MemberOut]:
    rows = (
        await session.execute(
            select(User, Membership)
            .join(Membership, Membership.user_id == User.id)
            .where(Membership.org_id == org_id)
            .order_by(Membership.created_at)
        )
    ).all()
    return [
        MemberOut(
            user_id=u.id, email=u.email, full_name=u.full_name, role=m.role, created_at=m.created_at
        )
        for u, m in rows
    ]


@router.post("", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
async def add_member(
    org_id: uuid.UUID,
    body: AddMemberRequest,
    _m=Depends(require_role(Role.owner)),
    session: AsyncSession = Depends(get_session),
) -> MemberOut:
    user = (
        await session.execute(select(User).where(User.email == body.email.lower()))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no user with that email (they must register first)")
    if (
        await session.execute(
            select(Membership.id).where(Membership.org_id == org_id, Membership.user_id == user.id)
        )
    ).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "already a member")

    m = Membership(org_id=org_id, user_id=user.id, role=body.role)
    session.add(m)
    await session.commit()
    return MemberOut(
        user_id=user.id, email=user.email, full_name=user.full_name, role=m.role, created_at=m.created_at
    )


@router.patch("/{user_id}", response_model=MemberOut)
async def update_member_role(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    body: UpdateRoleRequest,
    _m=Depends(require_role(Role.owner)),
    session: AsyncSession = Depends(get_session),
) -> MemberOut:
    m = (
        await session.execute(
            select(Membership).where(Membership.org_id == org_id, Membership.user_id == user_id)
        )
    ).scalar_one_or_none()
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "member not found")
    if m.role == Role.owner and body.role != Role.owner and await _owner_count(session, org_id) <= 1:
        raise HTTPException(status.HTTP_409_CONFLICT, "cannot demote the last owner")
    m.role = body.role
    await session.commit()
    user = await session.get(User, user_id)
    return MemberOut(
        user_id=user_id, email=user.email, full_name=user.full_name, role=m.role, created_at=m.created_at
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    _m=Depends(require_role(Role.owner)),
    session: AsyncSession = Depends(get_session),
):
    m = (
        await session.execute(
            select(Membership).where(Membership.org_id == org_id, Membership.user_id == user_id)
        )
    ).scalar_one_or_none()
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "member not found")
    if m.role == Role.owner and await _owner_count(session, org_id) <= 1:
        raise HTTPException(status.HTTP_409_CONFLICT, "cannot remove the last owner")
    await session.delete(m)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
