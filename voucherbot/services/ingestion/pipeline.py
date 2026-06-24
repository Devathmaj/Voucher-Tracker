"""
Shared processing pipeline: Collect → Normalize → Deduplicate → Keyword Score → Status

All providers produce NormalizedPost objects. Everything after collection
is provider-agnostic and reused across Reddit, RSS, and Website sources.
"""
import asyncio
import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from voucherbot.models.source import Source, SourceType
from voucherbot.models.post import Post, PostStatus
from voucherbot.models.keyword import Keyword
from voucherbot.providers.base import BaseCollector, NormalizedPost
from voucherbot.config.settings import settings
from voucherbot.services.ai.analyzer import analyze_post

logger = structlog.get_logger(__name__)

# Minimum cumulative keyword score to be queued for AI analysis
SCORE_THRESHOLD = 1


async def run_pipeline(
    db: AsyncSession,
    source_type: SourceType,
    collectors: dict[str, BaseCollector],
    fetch_limit: int = 25,
) -> dict:
    """
    Run the full ingestion pipeline for all enabled sources of a given type.
    `collectors` is a dict mapping a string key (e.g., 'rss', 'web', 'reddit') to a BaseCollector.
    """
    sync_id = f"Sync-{str(uuid.uuid4())[:8]}"
    start_time = datetime.now(timezone.utc)

    # Load enabled sources of this type
    result = await db.execute(
        select(Source).where(Source.enabled == True, Source.type == source_type)
    )
    all_sources = result.scalars().all()
    sources = [source for source in all_sources if _source_due(source)]

    # Load enabled keywords with scores
    kw_result = await db.execute(select(Keyword).where(Keyword.enabled == True))
    keywords: list[Keyword] = kw_result.scalars().all()

    stats = {
        "sources": len(sources),
        "skipped": len(all_sources) - len(sources),
        "fetched": 0,
        "new": 0,
        "duplicates": 0,
        "queued": 0,
        "filtered": 0,
        "ai_analyzed": 0,
        "errors": 0,
    }
    semaphore = asyncio.Semaphore(settings.reddit_concurrency_limit)

    async def process_source(source: Source):
        async with semaphore:
            try:
                # Determine the correct collector based on config structure
                config = source.config or {}
                collector = None
                if source.type == SourceType.REDDIT:
                    collector = collectors.get("reddit")
                elif "feed_url" in config:
                    collector = collectors.get("rss")
                elif "article_selector" in config:
                    collector = collectors.get("web")
                
                if not collector:
                    logger.error(f"{sync_id} No suitable collector found for {source.name}")
                    stats["errors"] += 1
                    return

                s_stats = await _process_one_source(db, source, collector, keywords, fetch_limit)
                for k, v in s_stats.items():
                    stats[k] += v
            except Exception as e:
                logger.error(f"{sync_id} Error on {source.name}", error=str(e))
                stats["errors"] += 1
                source.error_count += 1
                await db.commit()

    if sources:
        await asyncio.gather(*[process_source(s) for s in sources])

    duration = (datetime.now(timezone.utc) - start_time).total_seconds()
    logger.info(
        f"{sync_id} [{source_type.value}] complete",
        duration=f"{duration:.1f}s",
        **stats
    )
    return stats


def _source_due(source: Source) -> bool:
    config = source.config or {}
    interval = config.get("poll_interval_minutes")
    if not interval or not source.last_checked_utc:
        return True

    try:
        interval_minutes = int(interval)
    except (TypeError, ValueError):
        logger.warning("pipeline: invalid source poll interval", source=source.name, interval=interval)
        return True

    now = datetime.now(timezone.utc)
    last_checked = source.last_checked_utc
    if last_checked.tzinfo is None:
        last_checked = last_checked.replace(tzinfo=timezone.utc)

    elapsed_minutes = (now - last_checked).total_seconds() / 60
    return elapsed_minutes >= interval_minutes


async def _process_one_source(
    db: AsyncSession,
    source: Source,
    collector: BaseCollector,
    keywords: list[Keyword],
    fetch_limit: int,
) -> dict:
    stats = {"fetched": 0, "new": 0, "duplicates": 0, "queued": 0, "filtered": 0, "ai_analyzed": 0}

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

        if status == PostStatus.FILTERED:
            stats["filtered"] += 1
            continue

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
            stats["queued"] += 1

            # --- AI Analysis ---
            # Only run for freshly inserted posts to avoid re-analyzing duplicates.
            ai_result = await analyze_post(title=post.title, content=post.content)
            if ai_result is not None:
                # Fetch the newly inserted row so we can update it
                inserted = await db.execute(
                    select(Post)
                    .where(Post.source_id == source.id, Post.external_id == post.external_id)
                )
                db_post = inserted.scalars().first()
                if db_post:
                    db_post.ai_result = ai_result
                    db_post.status = PostStatus.PROCESSED
                    stats["ai_analyzed"] += 1
                    logger.debug(
                        "pipeline: ai analysis saved",
                        post_external_id=post.external_id,
                        is_voucher=ai_result.get("is_voucher"),
                        confidence=ai_result.get("confidence"),
                    )

    # 3. Update source last_checked_utc
    source.last_checked_utc = datetime.now(timezone.utc)
    source.error_count = 0
    await db.commit()

    return stats
