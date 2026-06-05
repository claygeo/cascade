"""Shared FastAPI dependencies: authentication + org-scoped authorization.

Tenant scope is **always derived server-side**: an endpoint takes ``org_id``
from the path, and ``get_membership`` proves the authenticated user actually
belongs to that org before anything else runs. A client can never act on an
org it isn't a member of, regardless of what it sends.
"""
from __future__ import annotations

import uuid

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.security import decode_access_token
from ..db import get_session
from ..enums import ROLE_RANK, Role
from ..models import Membership, User

_bearer = HTTPBearer(auto_error=True)


async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> User:
    try:
        payload = decode_access_token(creds.credentials)
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired token") from None

    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found or inactive")
    return user


async def get_membership(
    org_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Membership:
    membership = (
        await session.execute(
            select(Membership).where(
                Membership.org_id == org_id, Membership.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if membership is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not a member of this organization")
    return membership


def require_role(min_role: Role):
    """Dependency factory: require at least ``min_role`` in the path's org."""

    async def _checker(membership: Membership = Depends(get_membership)) -> Membership:
        if ROLE_RANK[membership.role] < ROLE_RANK[min_role]:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, f"requires '{min_role}' role or higher"
            )
        return membership

    return _checker
