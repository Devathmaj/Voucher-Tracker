from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from voucherbot.database.connection import get_session
from voucherbot.models.post import Post, PostStatus

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("")
async def get_alerts(
    limit: int = Query(default=25, ge=1, le=100),
    min_score: int = Query(default=4, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    stmt = (
        select(Post)
        .options(selectinload(Post.source))
        .where(Post.status.in_([PostStatus.PROCESSED, PostStatus.QUEUED]))
        .where(Post.score >= min_score)
        .order_by(Post.created_at.desc())
        .limit(limit * 3)
    )
    result = await session.execute(stmt)
    posts = result.scalars().all()

    alerts = [
        post
        for post in posts
        if _is_ai_positive(post) or (post.ai_result is None and post.score >= min_score)
    ][:limit]

    return [
        {
            "id": post.id,
            "title": post.title,
            "url": post.url,
            "source_name": post.source.name if post.source else None,
            "source_type": post.source.type.value if post.source else None,
            "score": post.score,
            "confidence": (post.ai_result or {}).get("confidence"),
            "voucher_code": (post.ai_result or {}).get("voucher_code"),
            "reason": (post.ai_result or {}).get("reason"),
            "published_at": post.published_at,
            "created_at": post.created_at,
        }
        for post in alerts
    ]


def _is_ai_positive(post: Post) -> bool:
    result = post.ai_result or {}
    return result.get("is_voucher") is True
