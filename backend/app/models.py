"""SQLAlchemy ORM models (all in the ``cascade`` schema).

The run/step_run tables implement a **lease-based** queue so the background
worker is crash-safe: a worker claims a run, stamps ``claimed_by`` +
``lease_expires_at``, and heartbeats while it works. If a worker dies, its lease
expires and another worker reclaims the run (see ``app/worker``).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .config import settings
from .db import Base
from .enums import Role, RunStatus, RunTrigger, StepStatus, StepType

_SCHEMA = settings.db_schema


def _fk(target: str, **kw) -> ForeignKey:
    """Schema-qualified foreign key (e.g. ``cascade.users.id``)."""
    return ForeignKey(f"{_SCHEMA}.{target}", **kw)


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


_ROLE_VALUES = ", ".join(f"'{r}'" for r in Role)
_STEP_VALUES = ", ".join(f"'{s}'" for s in StepType)
_RUN_STATUS_VALUES = ", ".join(f"'{s}'" for s in RunStatus)
_STEP_STATUS_VALUES = ", ".join(f"'{s}'" for s in StepStatus)
_TRIGGER_VALUES = ", ".join(f"'{t}'" for t in RunTrigger)


class Org(Base):
    __tablename__ = "orgs"

    id: Mapped[uuid.UUID] = _pk()
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    created_at: Mapped[datetime] = _created_at()

    memberships: Mapped[list[Membership]] = relationship(
        back_populates="org", cascade="all, delete-orphan"
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _pk()
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    created_at: Mapped[datetime] = _created_at()

    memberships: Mapped[list[Membership]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("org_id", "user_id", name="uq_membership_org_user"),
        CheckConstraint(f"role in ({_ROLE_VALUES})", name="ck_membership_role"),
    )

    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = mapped_column(_fk("orgs.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(_fk("users.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), server_default=text("'viewer'"), nullable=False)
    created_at: Mapped[datetime] = _created_at()

    org: Mapped[Org] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="memberships")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = _pk()
    user_id: Mapped[uuid.UUID] = mapped_column(_fk("users.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created_at()


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = mapped_column(_fk("orgs.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(140), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_sample: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(_fk("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    steps: Mapped[list[WorkflowStep]] = relationship(
        back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="WorkflowStep.position",
    )


class WorkflowStep(Base):
    __tablename__ = "workflow_steps"
    __table_args__ = (
        UniqueConstraint("workflow_id", "position", name="uq_step_workflow_position"),
        CheckConstraint(f"type in ({_STEP_VALUES})", name="ck_step_type"),
    )

    id: Mapped[uuid.UUID] = _pk()
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        _fk("workflows.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"), nullable=False)
    created_at: Mapped[datetime] = _created_at()

    workflow: Mapped[Workflow] = relationship(back_populates="steps")


class ProviderKey(Base):
    """A Bring-Your-Own-Key secret (Fernet-encrypted at rest)."""

    __tablename__ = "provider_keys"

    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = mapped_column(_fk("orgs.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), server_default=text("'openrouter'"), nullable=False)
    encrypted_key: Mapped[str] = mapped_column(Text, nullable=False)
    last4: Mapped[str] = mapped_column(String(8), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(_fk("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = _created_at()


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = (
        CheckConstraint(f"status in ({_RUN_STATUS_VALUES})", name="ck_run_status"),
        CheckConstraint(f"trigger in ({_TRIGGER_VALUES})", name="ck_run_trigger"),
        # The worker's claim query orders queued/expired runs by creation time.
        Index("ix_runs_status_created", "status", "created_at"),
        Index("ix_runs_org_created", "org_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = _pk()
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        _fk("workflows.id", ondelete="CASCADE"), nullable=False
    )
    # Denormalized for tenant-scoped reads without a join.
    org_id: Mapped[uuid.UUID] = mapped_column(_fk("orgs.id", ondelete="CASCADE"), nullable=False)

    status: Mapped[str] = mapped_column(String(20), server_default=text("'queued'"), nullable=False)
    trigger: Mapped[str] = mapped_column(String(20), server_default=text("'manual'"), nullable=False)

    input: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"), nullable=False)
    output: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)

    # --- lease-based queue / crash recovery ---
    attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    claimed_by: Mapped[str | None] = mapped_column(String(80))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # null provider_key_id => use the server's shared OpenRouter key (sample runs)
    provider_key_id: Mapped[uuid.UUID | None] = mapped_column(
        _fk("provider_keys.id", ondelete="SET NULL")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(_fk("users.id", ondelete="SET NULL"))

    created_at: Mapped[datetime] = _created_at()
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    step_runs: Mapped[list[StepRun]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="StepRun.position",
    )


class StepRun(Base):
    __tablename__ = "step_runs"
    __table_args__ = (
        CheckConstraint(f"status in ({_STEP_STATUS_VALUES})", name="ck_step_run_status"),
        Index("ix_step_runs_run_position", "run_id", "position"),
    )

    id: Mapped[uuid.UUID] = _pk()
    run_id: Mapped[uuid.UUID] = mapped_column(_fk("runs.id", ondelete="CASCADE"), nullable=False)
    # Keep step history even if the workflow step is later deleted.
    step_id: Mapped[uuid.UUID | None] = mapped_column(_fk("workflow_steps.id", ondelete="SET NULL"))
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(20), server_default=text("'pending'"), nullable=False)

    input: Mapped[dict | None] = mapped_column(JSONB)
    output: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    logs: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"), nullable=False)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = _created_at()

    run: Mapped[Run] = relationship(back_populates="step_runs")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(40))
    target_id: Mapped[str | None] = mapped_column(String(80))
    meta: Mapped[dict] = mapped_column("meta", JSONB, server_default=text("'{}'::jsonb"), nullable=False)
    created_at: Mapped[datetime] = _created_at()
