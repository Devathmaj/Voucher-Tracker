from typing import Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voucherbot.database.connection import get_session
from voucherbot.models.post import VoucherPost

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("")
async def get_alerts(
    limit: int = Query(default=25, ge=1, le=100),
    min_score: int = Query(default=0, ge=0),
    notified: bool | None = Query(
        default=None,
        description="Filter by is_notified; omit for all vouchers",
    ),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """Return AI-confirmed vouchers from the ``voucher_posts`` view."""
    stmt = select(VoucherPost).where(VoucherPost.score >= min_score)
    if notified is not None:
        stmt = stmt.where(VoucherPost.is_notified.is_(notified))
    stmt = stmt.order_by(VoucherPost.created_at.desc()).limit(limit)

    result = await session.execute(stmt)
    rows = result.scalars().all()

    return [
        {
            "id": row.id,
            "title": row.title,
            "url": row.url,
            "score": row.score,
            "status": row.status.value if row.status else None,
            "is_notified": row.is_notified,
            "vendor": row.vendor,
            "promotion_name": row.promotion_name,
            "promotion_type": row.promotion_type,
            "voucher_code": row.voucher_code,
            "discount": row.discount,
            "registration_url": row.registration_url,
            "confidence": row.confidence,
            "reason": row.reason,
            "event_id": row.event_id,
            "published_at": row.published_at,
            "created_at": row.created_at,
        }
        for row in rows
    ]
