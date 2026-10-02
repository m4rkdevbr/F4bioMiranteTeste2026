"""Async PostgreSQL access via asyncpg (no C-extension dependency beyond asyncpg)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg

from modernization_pipeline.config import get_settings

_pool: asyncpg.Pool | None = None


def _dsn() -> str:
    settings = get_settings()
    url = settings.database_url_sync
    # Accept SQLAlchemy-style URLs and normalize for asyncpg
    return (
        url.replace("postgresql+asyncpg://", "postgresql://")
        .replace("postgres+asyncpg://", "postgresql://")
    )


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(dsn=_dsn(), min_size=1, max_size=5)
    return _pool


@asynccontextmanager
async def connection_scope() -> AsyncIterator[asyncpg.Connection]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            yield conn


async def dispose_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def check_postgres() -> bool:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return True
    except Exception:
        return False
