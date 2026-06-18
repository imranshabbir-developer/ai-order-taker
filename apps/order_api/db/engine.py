from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from apps.order_api.settings import get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_database() -> None:
    global _engine, _session_factory
    settings = get_settings()
    if not settings.database_enabled:
        return

    _engine = create_async_engine(
        settings.async_database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)


async def close_database() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


def database_configured() -> bool:
    return _session_factory is not None


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("Database is not configured. Set DATABASE_URL in .env")
    async with _session_factory() as session:
        yield session


async def check_database() -> bool:
    if _session_factory is None:
        return False
    try:
        async with get_db_session() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
