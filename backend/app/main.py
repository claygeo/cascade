"""FastAPI application factory + wiring."""
from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .api import auth, keys, orgs, public, runs, workflows
from .config import settings
from .db import engine
from .logging_config import configure_logging, get_logger

configure_logging()
log = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("startup", environment=settings.environment, schema=settings.db_schema)
    worker_stop: asyncio.Event | None = None
    worker_task: asyncio.Task | None = None
    if settings.run_worker_in_process:
        from .worker import worker_loop

        worker_stop = asyncio.Event()
        worker_task = asyncio.create_task(worker_loop(worker_stop))
        log.info("in_process_worker_started")
    yield
    if worker_stop is not None:
        worker_stop.set()
    if worker_task is not None:
        try:
            await asyncio.wait_for(worker_task, timeout=10)
        except (TimeoutError, asyncio.CancelledError):
            pass
    await engine.dispose()
    log.info("shutdown")


app = FastAPI(
    title="Cascade API",
    version="0.1.0",
    summary="AI Workflow Builder — design, run, and monitor LLM workflows.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    structlog.contextvars.bind_contextvars(request_id=request_id)
    try:
        response = await call_next(request)
    finally:
        structlog.contextvars.clear_contextvars()
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok", "environment": settings.environment}


@app.get("/", tags=["meta"])
async def root() -> dict:
    return {"name": "Cascade API", "docs": "/docs", "health": "/health"}


for _router in (
    auth.router,
    orgs.router,
    workflows.router,
    keys.router,
    runs.router,
    public.router,
):
    app.include_router(_router, prefix="/api/v1")
