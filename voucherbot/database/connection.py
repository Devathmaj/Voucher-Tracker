from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from typing import AsyncGenerator

from voucherbot.config.settings import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=2,
    max_overflow=3,
    pool_timeout=30,
    pool_recycle=240,   # Supabase drops idle connections at ~300s
    pool_pre_ping=True, # detect dead connections before use
)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
