"""Auth router: register, login, refresh-token rotation, logout, me."""
from __future__ import annotations

import re
import secrets
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    refresh_expiry,
    verify_password,
)
from ..db import get_session
from ..enums import Role
from ..models import Membership, Org, RefreshToken, User
from ..schemas import (
    LoginRequest,
    MeOut,
    OrgOut,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserOut,
)
from .deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "workspace"


async def _unique_slug(session: AsyncSession, base: str) -> str:
    slug = base
    for _ in range(6):
        exists = (await session.execute(select(Org.id).where(Org.slug == slug))).first()
        if exists is None:
            return slug
        slug = f"{base}-{secrets.token_hex(2)}"
    return f"{base}-{secrets.token_hex(4)}"


async def _issue_tokens(session: AsyncSession, user: User) -> TokenPair:
    """Mint a stateless access JWT + an opaque refresh token (hash persisted)."""
    raw_refresh = generate_refresh_token()
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(raw_refresh),
            expires_at=refresh_expiry(),
        )
    )
    await session.commit()
    return TokenPair(access_token=create_access_token(str(user.id)), refresh_token=raw_refresh)


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, session: AsyncSession = Depends(get_session)) -> TokenPair:
    email = body.email.lower()
    if (await session.execute(select(User.id).where(User.email == email))).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "email already registered")

    user = User(email=email, password_hash=hash_password(body.password), full_name=body.full_name)
    session.add(user)
    await session.flush()

    default_name = body.full_name or email.split("@")[0]
    org_name = body.org_name or f"{default_name}'s workspace"
    org = Org(name=org_name, slug=await _unique_slug(session, _slugify(org_name)))
    session.add(org)
    await session.flush()

    session.add(Membership(org_id=org.id, user_id=user.id, role=Role.owner))
    return await _issue_tokens(session, user)


@router.post("/login", response_model=TokenPair)
async def login(body: LoginRequest, session: AsyncSession = Depends(get_session)) -> TokenPair:
    user = (
        await session.execute(select(User).where(User.email == body.email.lower()))
    ).scalar_one_or_none()
    # verify_password on a dummy-less path; constant-ish behavior either way.
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid email or password")
    return await _issue_tokens(session, user)


@router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshRequest, session: AsyncSession = Depends(get_session)) -> TokenPair:
    rt = (
        await session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == hash_token(body.refresh_token))
        )
    ).scalar_one_or_none()
    now = datetime.now(UTC)
    if rt is None or rt.revoked_at is not None or rt.expires_at <= now:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired refresh token")

    rt.revoked_at = now  # rotation: single-use refresh tokens
    user = await session.get(User, rt.user_id)
    if user is None or not user.is_active:
        await session.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found or inactive")
    return await _issue_tokens(session, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: RefreshRequest, session: AsyncSession = Depends(get_session)):
    rt = (
        await session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == hash_token(body.refresh_token))
        )
    ).scalar_one_or_none()
    if rt is not None and rt.revoked_at is None:
        rt.revoked_at = datetime.now(UTC)
        await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=MeOut)
async def me(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> MeOut:
    rows = (
        await session.execute(
            select(Org, Membership.role)
            .join(Membership, Membership.org_id == Org.id)
            .where(Membership.user_id == user.id)
            .order_by(Org.created_at)
        )
    ).all()
    orgs = [OrgOut(id=o.id, name=o.name, slug=o.slug, role=role) for o, role in rows]
    return MeOut(user=UserOut.model_validate(user), orgs=orgs)
