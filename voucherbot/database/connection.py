from contextlib import asynccontextmanager
from typing import AsyncGenerator, AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from voucherbot.config.settings import settings

# Keep pool_recycle short (60 s) to stay ahead of PgBouncer's
# server_idle_timeout / server_lifetime.  Connections idling longer
# than that can be killed by the pooler mid-transaction.
engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=2,
    max_overflow=3,
    pool_timeout=30,
    pool_recycle=60,
    pool_pre_ping=True,
    connect_args={"server_settings": {"statement_timeout": "120000"}},
)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False,
)


# ── Helpers that explicitly set statement_timeout ───────────────────────
# PgBouncer in transaction mode runs DISCARD ALL / RESET ALL after every
# COMMIT, which wipes session-level SETs, including statement_timeout.
# We therefore re-apply it on every new transaction so that long-running
# operations (bootstrap, RSS collection, AI analysis) don't hit Supabase's
# default 30 s limit.

_STMT_TIMEOUT = text("SET statement_timeout = '120000'")


async def _apply_timeout(session: AsyncSession) -> None:
    await session.execute(_STMT_TIMEOUT)


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Context manager that yields an :class:`AsyncSession` with a 120 s
    ``statement_timeout`` already applied.

    Usage::

        async with session_scope() as session:
            await session.execute(...)
            await session.commit()
    """
    async with AsyncSessionLocal() as session:
        await _apply_timeout(session)
        yield session


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a session with a 120 s statement_timeout."""
    async with session_scope() as session:
        yield session
