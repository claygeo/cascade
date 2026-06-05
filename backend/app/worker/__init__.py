"""Crash-safe background worker.

A worker claims one run at a time with ``SELECT ... FOR UPDATE SKIP LOCKED``,
extending a **lease** via a heartbeat while it executes. The same claim query
also reclaims runs whose lease has expired — so if a worker dies mid-run,
another worker picks the run up and re-runs it (execution is idempotent). On a
step failure the run is retried up to ``max_attempts`` before being marked
failed.

Two ways to run the loop:
* Standalone process (production):  ``python -m app.worker``
* In-process inside the API (cheap single-instance demos): set
  ``RUN_WORKER_IN_PROCESS=true`` — the API lifespan calls ``worker_loop``.
"""
from __future__ import annotations

import asyncio
import signal

from sqlalchemy import text

from ..config import settings
from ..db import SessionLocal, engine
from ..enums import RunStatus
from ..logging_config import configure_logging, get_logger
from ..models import Run
from ..seed import seed_sample_workflow
from ..services.runner import RunExecutionError, RunExecutor
from .clock import utcnow

log = get_logger("worker")

# Claim a queued run OR reclaim one whose lease has expired (crashed worker).
_CLAIM_SQL = text(
    f"""
    UPDATE {settings.db_schema}.runs
       SET status = 'running',
           claimed_by = :worker,
           attempts = attempts + 1,
           lease_expires_at = now() + (:lease * interval '1 second'),
           heartbeat_at = now(),
           started_at = COALESCE(started_at, now())
     WHERE id = (
            SELECT id FROM {settings.db_schema}.runs
             WHERE status = 'queued'
                OR (status = 'running' AND lease_expires_at < now())
             ORDER BY created_at
             FOR UPDATE SKIP LOCKED
             LIMIT 1
     )
    RETURNING id
    """
)

_HEARTBEAT_SQL = text(
    f"""
    UPDATE {settings.db_schema}.runs
       SET heartbeat_at = now(),
           lease_expires_at = now() + (:lease * interval '1 second')
     WHERE id = :id AND claimed_by = :worker AND status = 'running'
    """
)


async def _claim_one(worker_id: str) -> Run | None:
    async with SessionLocal() as session:
        row = (
            await session.execute(
                _CLAIM_SQL, {"worker": worker_id, "lease": settings.run_lease_seconds}
            )
        ).first()
        await session.commit()
        if row is None:
            return None
        return await session.get(Run, row[0])


async def _heartbeat(run_id, worker_id: str, stop: asyncio.Event) -> None:
    interval = max(settings.run_lease_seconds / 3, 5)
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except TimeoutError:
            pass
        if stop.is_set():
            break
        try:
            async with SessionLocal() as session:
                await session.execute(
                    _HEARTBEAT_SQL,
                    {"id": run_id, "worker": worker_id, "lease": settings.run_lease_seconds},
                )
                await session.commit()
        except Exception as exc:  # heartbeat must never crash the worker
            log.warning("heartbeat_failed", run_id=str(run_id), error=str(exc))


async def _process(run: Run, worker_id: str) -> None:
    stop = asyncio.Event()
    hb = asyncio.create_task(_heartbeat(run.id, worker_id, stop))
    log.info("run_claimed", run_id=str(run.id), attempt=run.attempts, trigger=run.trigger)
    try:
        async with SessionLocal() as session:
            run = await session.get(Run, run.id)
            executor = RunExecutor(session, settings)
            try:
                await executor.execute(run)
                run.status = RunStatus.succeeded
                run.finished_at = utcnow()
                await session.commit()
                log.info("run_succeeded", run_id=str(run.id))
            except RunExecutionError as exc:
                if run.attempts >= run.max_attempts:
                    run.status = RunStatus.failed
                    run.error = str(exc)
                    run.finished_at = utcnow()
                    log.warning("run_failed", run_id=str(run.id), error=str(exc))
                else:
                    # Requeue: clear the lease so another claim picks it up.
                    run.status = RunStatus.queued
                    run.claimed_by = None
                    run.lease_expires_at = None
                    run.error = str(exc)
                    log.info("run_requeued", run_id=str(run.id), attempt=run.attempts)
                await session.commit()
    finally:
        stop.set()
        await hb


async def worker_loop(stop: asyncio.Event, *, seed: bool = True) -> None:
    """The claim→execute→finalize loop. Runs until ``stop`` is set."""
    if seed:
        try:
            await seed_sample_workflow()
        except Exception as exc:
            log.warning("seed_failed", error=str(exc))

    log.info("worker_loop_start", worker_id=settings.worker_id, lease_seconds=settings.run_lease_seconds)
    while not stop.is_set():
        try:
            run = await _claim_one(settings.worker_id)
        except Exception as exc:  # transient DB issue (e.g. schema not migrated yet)
            log.warning("claim_failed", error=str(exc))
            run = None
        if run is None:
            try:
                await asyncio.wait_for(stop.wait(), timeout=settings.worker_poll_interval_seconds)
            except TimeoutError:
                pass
            continue
        try:
            await _process(run, settings.worker_id)
        except Exception as exc:  # never let one bad run kill the loop
            log.warning("process_crashed", run_id=str(run.id), error=str(exc))
    log.info("worker_loop_stop")


async def run_worker() -> None:
    """Standalone entrypoint: install signal handlers, run the loop, clean up."""
    configure_logging()
    stop = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:  # Windows
            pass

    try:
        await worker_loop(stop)
    finally:
        await engine.dispose()
