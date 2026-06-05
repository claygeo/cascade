"""DB-backed integration tests (auth flow, run execution, crash recovery).

These require a real Postgres with the `cascade` schema migrated. Run with:

    RUN_DB_TESTS=1 DATABASE_URL=postgresql+asyncpg://... pytest tests/test_integration.py

They assume an empty `runs` table (the autouse fixture clears it) so the
single-worker drive is deterministic.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import text

pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_DB_TESTS"),
    reason="set RUN_DB_TESTS=1 with a real DATABASE_URL to run DB integration tests",
)

from app.config import settings  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.enums import RunStatus  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Run  # noqa: E402
from app.worker import _claim_one, _process  # noqa: E402


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture(autouse=True)
async def _clean_runs():
    async with SessionLocal() as s:
        await s.execute(text(f"DELETE FROM {settings.db_schema}.step_runs"))
        await s.execute(text(f"DELETE FROM {settings.db_schema}.runs"))
        await s.commit()
    yield


async def _register() -> tuple[str, dict]:
    email = f"user-{uuid.uuid4().hex[:10]}@example.com"
    async with _client() as c:
        r = await c.post("/api/v1/auth/register", json={"email": email, "password": "supersecret123"})
        assert r.status_code == 201, r.text
        return email, r.json()


async def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _make_offline_workflow(c: httpx.AsyncClient, org_id: str, token: str) -> str:
    """A transform -> output workflow: deterministic, no network or LLM."""
    payload = {
        "name": "echo",
        "steps": [
            {"type": "transform", "name": "shape", "config": {"template": {"v": "{{ input.n }}"}}},
            {"type": "output", "name": "result", "config": {"value": {"echo": "{{ steps.shape.output.result.v }}"}}},
        ],
    }
    r = await c.post(f"/api/v1/orgs/{org_id}/workflows", json=payload, headers=await _auth(token))
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _drive_until_done(run_id: str, worker_id: str = "test-worker", rounds: int = 30) -> Run:
    for _ in range(rounds):
        run = await _claim_one(worker_id)
        if run is not None:
            await _process(run, worker_id)
        async with SessionLocal() as s:
            mine = await s.get(Run, uuid.UUID(run_id))
            if mine and mine.status in (RunStatus.succeeded, RunStatus.failed):
                return mine
        if run is None:
            await asyncio.sleep(0.05)
    raise AssertionError("run did not reach a terminal state")


async def test_register_login_me():
    email, tokens = await _register()
    async with _client() as c:
        me = await c.get("/api/v1/auth/me", headers=await _auth(tokens["access_token"]))
        assert me.status_code == 200
        body = me.json()
        assert body["user"]["email"] == email
        assert len(body["orgs"]) == 1
        assert body["orgs"][0]["role"] == "owner"


async def test_login_rejects_bad_password():
    email, _ = await _register()
    async with _client() as c:
        r = await c.post("/api/v1/auth/login", json={"email": email, "password": "wrong-password"})
        assert r.status_code == 401


async def test_run_executes_end_to_end():
    _, tokens = await _register()
    token = tokens["access_token"]
    async with _client() as c:
        me = (await c.get("/api/v1/auth/me", headers=await _auth(token))).json()
        org_id = me["orgs"][0]["id"]
        wf_id = await _make_offline_workflow(c, org_id, token)
        r = await c.post(
            f"/api/v1/orgs/{org_id}/workflows/{wf_id}/runs",
            json={"input": {"n": 21}},
            headers=await _auth(token),
        )
        assert r.status_code == 202, r.text
        run_id = r.json()["id"]

    run = await _drive_until_done(run_id)
    assert run.status == RunStatus.succeeded
    assert run.output["result"]["echo"] == 21


async def test_cross_tenant_access_is_forbidden():
    # User A creates a workflow; user B (different org) must not read it.
    _, ta = await _register()
    _, tb = await _register()
    async with _client() as c:
        me_a = (await c.get("/api/v1/auth/me", headers=await _auth(ta["access_token"]))).json()
        org_a = me_a["orgs"][0]["id"]
        wf_id = await _make_offline_workflow(c, org_a, ta["access_token"])
        # B tries to read A's workflow under A's org id -> not a member -> 403
        r = await c.get(f"/api/v1/orgs/{org_a}/workflows/{wf_id}", headers=await _auth(tb["access_token"]))
        assert r.status_code == 403


async def test_crash_recovery_reclaims_expired_lease():
    """The codex centerpiece: a worker dies mid-run, another reclaims + finishes."""
    _, tokens = await _register()
    token = tokens["access_token"]
    async with _client() as c:
        me = (await c.get("/api/v1/auth/me", headers=await _auth(token))).json()
        org_id = me["orgs"][0]["id"]
        wf_id = await _make_offline_workflow(c, org_id, token)
        run_id = (
            await c.post(
                f"/api/v1/orgs/{org_id}/workflows/{wf_id}/runs",
                json={"input": {"n": 7}},
                headers=await _auth(token),
            )
        ).json()["id"]

    # Simulate a worker that claimed the run then crashed: running + expired lease.
    async with SessionLocal() as s:
        run = await s.get(Run, uuid.UUID(run_id))
        run.status = RunStatus.running
        run.claimed_by = "dead-worker"
        run.attempts = 1
        run.lease_expires_at = datetime.now(UTC) - timedelta(seconds=120)
        await s.commit()

    # A healthy worker should reclaim the expired-lease run (not skip it).
    reclaimed = await _claim_one("healthy-worker")
    assert reclaimed is not None
    assert str(reclaimed.id) == run_id
    assert reclaimed.claimed_by == "healthy-worker"
    assert reclaimed.attempts == 2  # incremented on reclaim

    await _process(reclaimed, "healthy-worker")
    async with SessionLocal() as s:
        run = await s.get(Run, uuid.UUID(run_id))
        assert run.status == RunStatus.succeeded
        assert run.output["result"]["echo"] == 7
