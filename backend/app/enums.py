"""Domain enums. String-valued so they serialize cleanly to JSON and Postgres."""
from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    owner = "owner"
    editor = "editor"
    viewer = "viewer"


class StepType(StrEnum):
    http_fetch = "http_fetch"
    llm = "llm"
    transform = "transform"
    conditional = "conditional"
    output = "output"


class RunStatus(StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    canceled = "canceled"


class StepStatus(StrEnum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    skipped = "skipped"


class RunTrigger(StrEnum):
    manual = "manual"
    sample = "sample"


# Higher number == more privilege. Used for role-gated endpoints.
ROLE_RANK: dict[str, int] = {Role.viewer: 0, Role.editor: 1, Role.owner: 2}
