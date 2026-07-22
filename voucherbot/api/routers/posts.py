from typing import Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from voucherbot.database.connection import get_session
from voucherbot.models.post import Post, PostStatus
from voucherbot.models.source import Source, SourceType

router = APIRouter(prefix="/posts", tags=["posts"])


@router.get("")
async def get_posts(
    status: PostStatus | None = Query(default=None),
    source_type: SourceType | None = Query(default=None),
    min_score: int | None = Query(default=None, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    stmt = (
        select(Post)
        .options(selectinload(Post.source))
        .order_by(Post.published_at.desc().nullslast(), Post.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    if status is not None:
        stmt = stmt.where(Post.status == status)
    if min_score is not None:
        stmt = stmt.where(Post.score >= min_score)
    if source_type is not None:
        stmt = stmt.join(Source).where(Source.type == source_type)

    result = await session.execute(stmt)
    posts = result.scalars().all()

    return [_serialize_post(post) for post in posts]


def _serialize_post(post: Post) -> dict[str, Any]:
    return {
        "id": post.id,
        "source": {
            "id": post.source.id,
            "name": post.source.name,
            "type": post.source.type.value,
        }
        if post.source
        else None,
        "external_id": post.external_id,
        "url": post.url,
        "title": post.title,
        "summary": post.summary,
        "author": post.author,
        "published_at": post.published_at,
        "status": post.status.value,
        "score": post.score,
        "ai_result": post.ai_result,
        "created_at": post.created_at,
        "updated_at": post.updated_at,
    }
