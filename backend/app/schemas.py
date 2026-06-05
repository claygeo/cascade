"""Pydantic request/response schemas (API contracts)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .enums import Role, StepType


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --------------------------- Auth ---------------------------
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    full_name: str | None = Field(default=None, max_length=120)
    org_name: str | None = Field(default=None, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(ORMModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str | None = None
    created_at: datetime


class OrgOut(ORMModel):
    id: uuid.UUID
    name: str
    slug: str
    role: str | None = None  # requesting user's role in this org


class MeOut(BaseModel):
    user: UserOut
    orgs: list[OrgOut]


# ------------------------ Workflows -------------------------
class StepIn(BaseModel):
    type: StepType
    name: str = Field(min_length=1, max_length=120)
    config: dict[str, Any] = Field(default_factory=dict)


class StepOut(ORMModel):
    id: uuid.UUID
    position: int
    type: str
    name: str
    config: dict[str, Any]


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=140)
    description: str | None = Field(default=None, max_length=2000)
    steps: list[StepIn] = Field(default_factory=list)


class WorkflowUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=140)
    description: str | None = Field(default=None, max_length=2000)
    steps: list[StepIn] | None = None


class WorkflowSummary(ORMModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    description: str | None = None
    is_sample: bool
    created_at: datetime
    updated_at: datetime


class WorkflowOut(WorkflowSummary):
    steps: list[StepOut]


# --------------------------- Runs ---------------------------
class RunCreate(BaseModel):
    input: dict[str, Any] = Field(default_factory=dict)
    provider_key_id: uuid.UUID | None = None


class StepRunOut(ORMModel):
    id: uuid.UUID
    position: int
    type: str
    name: str
    status: str
    input: dict[str, Any] | None = None
    output: dict[str, Any] | None = None
    error: str | None = None
    logs: list[Any] = Field(default_factory=list)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None


class RunSummary(ORMModel):
    id: uuid.UUID
    workflow_id: uuid.UUID
    status: str
    trigger: str
    attempts: int
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None


class RunOut(RunSummary):
    input: dict[str, Any]
    output: dict[str, Any] | None = None
    step_runs: list[StepRunOut] = Field(default_factory=list)


# ----------------------- Provider keys ----------------------
class ProviderKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    key: str = Field(min_length=8, max_length=400)
    provider: str = "openrouter"


class ProviderKeyOut(ORMModel):
    id: uuid.UUID
    name: str
    provider: str
    last4: str
    created_at: datetime


# ------------------------- Members --------------------------
class AddMemberRequest(BaseModel):
    email: EmailStr
    role: Role = Role.viewer


class MemberOut(BaseModel):
    user_id: uuid.UUID
    email: EmailStr
    full_name: str | None = None
    role: str
    created_at: datetime


# ------------------------- Sample (public) ------------------
class SampleRunRequest(BaseModel):
    input: dict[str, Any] = Field(default_factory=dict)
