"""Run executor: walks a workflow's steps, persisting per-step progress to the
database as it goes so the UI can stream live status + logs.

Step-level state lives here; *run-level* lifecycle (claiming, leasing,
heartbeating, retry/finalize) lives in ``app/worker``. Re-executing a run is
idempotent — prior ``step_runs`` are cleared first, so a reclaimed/retried run
starts clean.
"""
from __future__ import annotations

import time
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..core.crypto import decrypt_secret
from ..enums import StepStatus, StepType
from ..logging_config import get_logger
from ..models import ProviderKey, Run, StepRun, WorkflowStep
from .engine import ExecContext, StepError, StepResult, execute_step
from .templating import TemplateError, render

log = get_logger("runner")


def _now() -> datetime:
    return datetime.now(UTC)


class RunExecutionError(Exception):
    """A step failed; carries the offending step name for run-level handling."""

    def __init__(self, step_name: str, message: str) -> None:
        self.step_name = step_name
        self.message = message
        super().__init__(f"step '{step_name}' failed: {message}")


class RunExecutor:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    async def _exec_context(self, run: Run) -> ExecContext:
        api_key = self.settings.openrouter_api_key  # server key (sample/demo runs)
        if run.provider_key_id:
            pk = await self.session.get(ProviderKey, run.provider_key_id)
            if pk is None:
                raise RunExecutionError("(setup)", "provider key not found")
            api_key = decrypt_secret(pk.encrypted_key)  # decrypted only in memory
        return ExecContext(
            api_key=api_key,
            base_url=self.settings.openrouter_base_url,
            default_model=self.settings.llm_default_model,
            max_output_tokens=self.settings.llm_max_output_tokens,
            llm_timeout=float(self.settings.llm_request_timeout_seconds),
            http_timeout=float(self.settings.http_fetch_timeout_seconds),
        )

    async def execute(self, run: Run) -> None:
        # Idempotent: a retried/reclaimed run starts from a clean slate.
        await self.session.execute(delete(StepRun).where(StepRun.run_id == run.id))
        await self.session.commit()

        steps = (
            await self.session.execute(
                select(WorkflowStep)
                .where(WorkflowStep.workflow_id == run.workflow_id)
                .order_by(WorkflowStep.position)
            )
        ).scalars().all()

        context: dict = {"input": run.input or {}, "steps": {}}
        ctx = await self._exec_context(run)
        final_output = None
        skip_remaining = False

        for step in steps:
            sr = StepRun(
                run_id=run.id,
                step_id=step.id,
                position=step.position,
                type=step.type,
                name=step.name,
                status=StepStatus.running,
                started_at=_now(),
            )
            self.session.add(sr)
            await self.session.flush()

            if skip_remaining:
                sr.status = StepStatus.skipped
                sr.finished_at = _now()
                sr.duration_ms = 0
                await self.session.commit()
                continue

            try:
                rendered = render(step.config or {}, context)
            except TemplateError as exc:
                await self._fail_step(sr, str(exc))
                raise RunExecutionError(step.name, str(exc)) from exc

            sr.input = rendered
            await self.session.commit()  # live: the UI now sees this step "running"

            t0 = time.monotonic()
            try:
                result: StepResult = await execute_step(step.type, step.name, rendered, ctx)
            except StepError as exc:
                await self._fail_step(sr, str(exc), int((time.monotonic() - t0) * 1000))
                raise RunExecutionError(step.name, str(exc)) from exc
            except Exception as exc:  # defensive: keep raw stacks out of run output
                await self._fail_step(sr, f"unexpected error: {exc}", int((time.monotonic() - t0) * 1000))
                raise RunExecutionError(step.name, str(exc)) from exc

            sr.status = StepStatus.succeeded
            sr.output = result.output
            sr.logs = result.logs
            sr.finished_at = _now()
            sr.duration_ms = int((time.monotonic() - t0) * 1000)
            await self.session.commit()

            entry = {"output": result.output}
            context["steps"][step.name] = entry
            context["steps"][str(step.position)] = entry  # allow index references too
            if step.type == StepType.output:
                final_output = result.output.get("result")
            if result.skip_rest:
                skip_remaining = True

        if final_output is None:
            named = [k for k in context["steps"] if not k.isdigit()]
            final_output = context["steps"][named[-1]]["output"] if named else {}
        run.output = {"result": final_output}

    async def _fail_step(self, sr: StepRun, message: str, duration_ms: int | None = None) -> None:
        sr.status = StepStatus.failed
        sr.error = message
        sr.finished_at = _now()
        if duration_ms is not None:
            sr.duration_ms = duration_ms
        logs = list(sr.logs or [])
        logs.append({"level": "error", "message": message})
        sr.logs = logs
        await self.session.commit()
