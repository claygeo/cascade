"""BYOK provider-key management. Keys are Fernet-encrypted at rest; the
plaintext is never returned or logged — only a non-sensitive ``last4``."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.crypto import encrypt_secret, last4
from ..db import get_session
from ..enums import Role
from ..models import ProviderKey, User
from ..schemas import ProviderKeyCreate, ProviderKeyOut
from .deps import get_current_user, get_membership, require_role

router = APIRouter(prefix="/orgs/{org_id}/keys", tags=["provider-keys"])


@router.get("", response_model=list[ProviderKeyOut])
async def list_keys(
    org_id: uuid.UUID,
    _m=Depends(get_membership),
    session: AsyncSession = Depends(get_session),
) -> list[ProviderKeyOut]:
    rows = (
        await session.execute(
            select(ProviderKey).where(ProviderKey.org_id == org_id).order_by(ProviderKey.created_at.desc())
        )
    ).scalars().all()
    return [ProviderKeyOut.model_validate(k) for k in rows]


@router.post("", response_model=ProviderKeyOut, status_code=status.HTTP_201_CREATED)
async def create_key(
    org_id: uuid.UUID,
    body: ProviderKeyCreate,
    _m=Depends(require_role(Role.editor)),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ProviderKeyOut:
    pk = ProviderKey(
        org_id=org_id,
        name=body.name,
        provider=body.provider,
        encrypted_key=encrypt_secret(body.key),
        last4=last4(body.key),
        created_by=user.id,
    )
    session.add(pk)
    await session.commit()
    return ProviderKeyOut.model_validate(pk)


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_key(
    org_id: uuid.UUID,
    key_id: uuid.UUID,
    _m=Depends(require_role(Role.editor)),
    session: AsyncSession = Depends(get_session),
):
    pk = (
        await session.execute(
            select(ProviderKey).where(ProviderKey.id == key_id, ProviderKey.org_id == org_id)
        )
    ).scalar_one_or_none()
    if pk is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "key not found")
    await session.delete(pk)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
