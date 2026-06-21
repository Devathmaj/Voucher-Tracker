"""
Shared processing pipeline: Collect → Normalize → Deduplicate → Keyword Score → Status

All providers produce NormalizedPost objects. Everything after collection
is provider-agnostic and reused across Reddit, RSS, and Website sources.
"""
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Type

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from voucherbot.models.source import Source, SourceType
from voucherbot.models.post import Post, PostStatus
from voucherbot.models.keyword import Keyword
from voucherbot.providers.base import BaseCollector, NormalizedPost
from voucherbot.config.settings import settings

logger = structlog.get_logger(__name__)

# Minimum cumulative keyword score to be queued for AI analysis
SCORE_THRESHOLD = 1


async def run_pipeline(
    db: AsyncSession,
    source_type: SourceType,
    collector: BaseCollector,
    fetch_limit: int = 25,
) -> dict:
    """
    Run the full ingestion pipeline for all enabled sources of a given type.
    Returns aggregate stats for logging.
    """
    sync_id = f"Sync-{str(uuid.uuid4())[:8]}"
    start_time = datetime.now(timezone.utc)

    # Load enabled sources of this type
    result = await db.execute(
        select(Source).where(Source.enabled == True, Source.type == source_type)
    )
    sources = result.scalars().all()

    # Load enabled keywords with scores
    kw_result = await db.execute(select(Keyword).where(Keyword.enabled == True))
    keywords: list[Keyword] = kw_result.scalars().all()

    stats = {"sources": len(sources), "fetched": 0, "new": 0, "duplicates": 0, "queued": 0, "filtered": 0, "errors": 0}
    semaphore = asyncio.Semaphore(settings.reddit_concurrency_limit)

    async def process_source(source: Source):
        async with semaphore:
            try:
                s_stats = await _process_one_source(db, source, collector, keywords, fetch_limit)
                for k, v in s_stats.items():
                    stats[k] += v
            except Exception as e:
                logger.error(f"{sync_id} Error on {source.name}", error=str(e))
                stats["errors"] += 1
                source.error_count += 1
                await db.commit()

    await asyncio.gather(*[process_source(s) for s in sources])

    duration = (datetime.now(timezone.utc) - start_time).total_seconds()
    logger.info(
        f"{sync_id} [{source_type.value}] complete",
        duration=f"{duration:.1f}s",
        **stats
    )
    return stats


async def _process_one_source(
    db: AsyncSession,
    source: Source,
    collector: BaseCollector,
    keywords: list[Keyword],
    fetch_limit: int,
) -> dict:
    stats = {"fetched": 0, "new": 0, "duplicates": 0, "queued": 0, "filtered": 0}

    # 1. Collect
    posts: list[NormalizedPost] = await collector.collect(
        source_config=source.config or {},
        limit=fetch_limit,
    )
    stats["fetched"] = len(posts)

    # 2. Deduplicate + Keyword Score + Upsert
    for post in posts:
        # 2a. Keyword scoring
        text = f"{post.title} {post.content or ''}".lower()
        score = sum(kw.score for kw in keywords if kw.keyword.lower() in text)
        status = PostStatus.QUEUED if score >= SCORE_THRESHOLD else PostStatus.FILTERED

        # 2b. Insert with ON CONFLICT DO NOTHING
        stmt = (
            insert(Post)
            .values(
                source_id=source.id,
                external_id=post.external_id,
                url=post.url,
                title=post.title,
                content=post.content,
                summary=post.summary,
                author=post.author,
                published_at=post.published_at,
                status=status,
                score=score,
                raw_data=post.raw_data,
            )
            .on_conflict_do_nothing(constraint="uq_posts_source_external")
        )
        result = await db.execute(stmt)

        if result.rowcount == 0:
            stats["duplicates"] += 1
        else:
            stats["new"] += 1
            if status == PostStatus.QUEUED:
                stats["queued"] += 1
            else:
                stats["filtered"] += 1

    # 3. Update source last_checked_utc
    source.last_checked_utc = datetime.now(timezone.utc)
    source.error_count = 0
    await db.commit()

    return stats
