from typing import Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voucherbot.database.connection import get_session
from voucherbot.models.source import Source, SourceType

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("")
async def get_sources(
    source_type: SourceType | None = Query(default=None),
    enabled: bool | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    stmt = select(Source).order_by(Source.priority.desc(), Source.name)
    if source_type is not None:
        stmt = stmt.where(Source.type == source_type)
    if enabled is not None:
        stmt = stmt.where(Source.enabled == enabled)

    result = await session.execute(stmt)
    sources = result.scalars().all()
    return [
        {
            "id": source.id,
            "name": source.name,
            "type": source.type.value,
            "base_url": source.base_url,
            "enabled": source.enabled,
            "priority": source.priority,
            "last_checked_utc": source.last_checked_utc,
            "error_count": source.error_count,
            "config": source.config,
        }
        for source in sources
    ]
