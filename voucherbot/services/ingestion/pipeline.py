"""
Shared processing pipeline: Collect → Keyword Filter → Doc Dedup → AI Extraction → Event Matching

Stage 1 — Document Deduplication (deterministic)
    Intra-batch duplicates removed in-memory (deduplicate_batch).
    Cross-source duplicates caught by the partial UNIQUE index on posts.content_hash.
    Exact duplicates are dropped before AI inference runs.

Stage 2 — AI Extraction
    Only posts that survived Stage 1 are sent to the AI analyzer.
    Returns a canonical ExtractedEvent (provider-agnostic).

Stage 3 — Canonical Event Matching
    AI-extracted data is scored against existing Events using configured weights.
    Score >= auto_merge_threshold  → attach to existing Event (AUTO_MERGED).
    Score in [possible_match, auto_merge) → POSSIBLE_MATCH (for future review).
    Score < possible_match_threshold → create new canonical Event.

All providers produce NormalizedPost objects. Everything after collection
is provider-agnostic and reused across Reddit, RSS, and Website sources.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from voucherbot.config.settings import settings
from voucherbot.models.keyword import Keyword
from voucherbot.models.post import Post, PostStatus
from voucherbot.models.source import Source, SourceType
from voucherbot.providers.base import BaseCollector, NormalizedPost
from voucherbot.services.ai.analyzer import analyze_post
from voucherbot.services.ingestion.dedup import content_hash, deduplicate_batch
from voucherbot.services.ingestion.event_matcher import EventMatcher

logger = structlog.get_logger(__name__)

# Minimum cumulative keyword score to be queued for AI analysis.
SCORE_THRESHOLD = 1

# Module-level EventMatcher instance (stateless, safe to share).
_event_matcher = EventMatcher()


async def run_pipeline(
    db: AsyncSession,
    source_type: SourceType,
    collectors: dict[str, BaseCollector],
    fetch_limit: int = 25,
) -> dict:
    """
    Run the full ingestion pipeline for all enabled sources of a given type.
    ``collectors`` maps a string key (e.g., 'rss', 'web', 'reddit') to a BaseCollector.
    """
    sync_id = f"Sync-{str(uuid.uuid4())[:8]}"
    start_time = datetime.now(timezone.utc)

    # Load enabled sources of this type.
    result = await db.execute(
        select(Source).where(Source.enabled == True, Source.type == source_type)  # noqa: E712
    )
    all_sources = result.scalars().all()
    sources = [source for source in all_sources if _source_due(source)]

    # Load enabled keywords with scores.
    kw_result = await db.execute(select(Keyword).where(Keyword.enabled == True))  # noqa: E712
    keywords: list[Keyword] = kw_result.scalars().all()

    stats = {
        "sources": len(sources),
        "skipped": len(all_sources) - len(sources),
        "fetched": 0,
        "keyword_filtered": 0,
        "doc_duplicates": 0,      # Stage 1: exact doc duplicates (same content_hash)
        "new_posts": 0,
        "ai_analyzed": 0,
        "events_created": 0,      # Stage 3: new Events created
        "events_attached": 0,     # Stage 3: Posts attached to existing Events
        "possible_matches": 0,    # Stage 3: flagged for future review
        "errors": 0,
    }
    semaphore = asyncio.Semaphore(settings.reddit_concurrency_limit)

    async def process_source(source: Source) -> None:
        async with semaphore:
            try:
                config = source.config or {}
                collector: BaseCollector | None = None
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

                s_stats = await _process_one_source(
                    db, source, collector, keywords, fetch_limit
                )
                for k, v in s_stats.items():
                    stats[k] += v
            except Exception as e:
                logger.error(f"{sync_id} Error on {source.name}", error=str(e))
                stats["errors"] += 1
                source.error_count += 1
                await db.commit()

    if sources:
        for s in sources:
            await process_source(s)

    duration = (datetime.now(timezone.utc) - start_time).total_seconds()
    logger.info(
        f"{sync_id} [{source_type.value}] complete",
        duration=f"{duration:.1f}s",
        **stats,
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
        logger.warning(
            "pipeline: invalid source poll interval",
            source=source.name,
            interval=interval,
        )
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
    stats = {
        "fetched": 0,
        "keyword_filtered": 0,
        "doc_duplicates": 0,
        "new_posts": 0,
        "ai_analyzed": 0,
        "events_created": 0,
        "events_attached": 0,
        "possible_matches": 0,
    }

    # ── Stage 0: Collect ──────────────────────────────────────────────────────
    posts: list[NormalizedPost] = await collector.collect(
        source_config=source.config or {},
        limit=fetch_limit,
    )
    stats["fetched"] = len(posts)

    # ── Keyword Filtering ─────────────────────────────────────────────────────
    scored: list[tuple[NormalizedPost, int]] = []
    for post in posts:
        text = f"{post.title} {post.content or ''}".lower()
        score = sum(kw.score for kw in keywords if kw.keyword.lower() in text)
        if score < SCORE_THRESHOLD:
            stats["keyword_filtered"] += 1
        else:
            scored.append((post, score))

    if not scored:
        source.last_checked_utc = datetime.now(timezone.utc)
        source.error_count = 0
        await db.commit()
        return stats

    # ── Stage 1: Document Deduplication (in-memory batch) ────────────────────
    # Compute content_hash for every surviving post.
    hashed: list[tuple[NormalizedPost, int, str]] = [
        (post, score, content_hash(post.title, post.url))
        for post, score in scored
    ]

    # Remove intra-batch duplicates (same content_hash within this pipeline run).
    seen_hashes: set[str] = set()
    deduped: list[tuple[NormalizedPost, int, str]] = []
    for post, score, ch in hashed:
        if ch in seen_hashes:
            stats["doc_duplicates"] += 1
        else:
            seen_hashes.add(ch)
            deduped.append((post, score, ch))

    # ── Stage 1 cont.: DB upsert with content_hash ───────────────────────────
    # We use ON CONFLICT DO NOTHING for uq_posts_source_external.
    # If the partial unique index on content_hash triggers a violation (because
    # another source already fetched the exact same document), it will raise an
    # IntegrityError which we catch and ignore.
    inserted_posts: list[tuple[NormalizedPost, Post]] = []
    
    from sqlalchemy.exc import IntegrityError

    for post, score, ch in deduped:
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
                status=PostStatus.QUEUED,
                score=score,
                raw_data=post.raw_data,
                content_hash=ch,
            )
            .on_conflict_do_nothing(constraint="uq_posts_source_external")
        )
        
        # In SQLAlchemy async, we must manage the savepoint ourselves if we
        # expect to catch and survive IntegrityErrors inside a transaction.
        async with db.begin_nested():
            try:
                result = await db.execute(stmt)
            except IntegrityError:
                # Caught uq_posts_content_hash violation
                stats["doc_duplicates"] += 1
                continue

        if result.rowcount == 0:
            # Caught uq_posts_source_external via ON CONFLICT DO NOTHING
            stats["doc_duplicates"] += 1
            continue

        # Fetch the newly inserted row (needed for event_id assignment later).
        inserted_row = await db.execute(
            select(Post).where(
                Post.source_id == source.id,
                Post.external_id == post.external_id,
            )
        )
        db_post = inserted_row.scalars().first()
        if db_post:
            stats["new_posts"] += 1
            inserted_posts.append((post, db_post))

    # ── Stage 2: AI Extraction ────────────────────────────────────────────────
    # Only runs on posts that survived Stage 1.
    for post, db_post in inserted_posts:
        extracted = await analyze_post(title=post.title, content=post.content)
        if extracted is None:
            # Provider unavailable; leave post status as QUEUED for retry.
            continue

        # Persist the raw AI result for debugging / audit.
        db_post.ai_result = extracted.model_dump()
        stats["ai_analyzed"] += 1

        if not extracted.is_voucher:
            db_post.status = PostStatus.FILTERED
            logger.debug(
                "pipeline: AI classified as non-voucher",
                post_id=db_post.id,
                confidence=extracted.confidence,
            )
            continue

        # ── Stage 3: Canonical Event Matching ─────────────────────────────────
        from voucherbot.models.event import MatchConfidence  # avoid circular at module top

        event, confidence = await _event_matcher.match_or_create(
            db, extracted, db_post, source.type
        )
        db_post.status = PostStatus.PROCESSED

        if confidence == MatchConfidence.NEW:
            stats["events_created"] += 1
        elif confidence == MatchConfidence.POSSIBLE_MATCH:
            stats["possible_matches"] += 1
        else:
            stats["events_attached"] += 1

    # ── Finalise ──────────────────────────────────────────────────────────────
    source.last_checked_utc = datetime.now(timezone.utc)
    source.error_count = 0
    await db.commit()

    return stats
