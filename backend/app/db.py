"""Async SQLAlchemy engine + session, scoped to the `cascade` schema.

Notes for reviewers:
* All ORM tables live in a dedicated Postgres schema (``settings.db_schema``)
  so this app can share a Supabase instance without colliding with other
  schemas. We set ``search_path`` on every connection.
* ``statement_cache_size=0`` keeps us compatible with Supabase's connection
  pooler (pgbouncer); ``pool_pre_ping`` + ``pool_recycle`` survive the pooler
  dropping idle connections. Use the **Session pooler** (port 5432) URL.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .config import settings

# Bind all metadata to the cascade schema.
metadata_obj = MetaData(schema=settings.db_schema)


class Base(DeclarativeBase):
    metadata = metadata_obj


_connect_args: dict = {
    "server_settings": {"search_path": f"{settings.db_schema},public"},
    "statement_cache_size": 0,
}
if settings.db_ssl_require:
    _connect_args["ssl"] = "require"

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args=_connect_args,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields a transactional session."""
    async with SessionLocal() as session:
        yield session
