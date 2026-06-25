"""
Background scheduler — conflict-free, resource-aware.

Design constraints
------------------
* Container budget: 512 MB RAM / 0.1 vCPU.
* Only ONE job may be executing at any time (a full pipeline run touches the DB,
  calls the AI API, and loops over potentially dozens of sources — running two
  concurrently would easily OOM or cause DB connection exhaustion).
* Jobs must never stack: if the previous run hasn't finished, skip the new tick
  (APScheduler ``max_instances=1`` + ``misfire_grace_time`` handles this).
* Stagger cold-start: spread the six job types across the first ~12 minutes so
  the process doesn't attempt six simultaneous DB + network round-trips the
  instant it boots.
* Add a small random jitter (±60 s) so that in a future multi-instance scenario
  the instances don't all wake up at exactly the same second.

Job cadence & stagger map (all times relative to scheduler start)
-----------------------------------------------------------------
  t +  0 s  │ Reddit    │ every 15 min  │ highest-frequency, first slot
  t +120 s   │ RSS       │ every 30 min  │ 2-min stagger
  t +240 s   │ Blogs     │ every 60 min  │ 4-min stagger
  t +360 s   │ Forums    │ every 2 h     │ 6-min stagger
  t +480 s   │ Websites  │ every 6 h     │ 8-min stagger
  t +600 s   │ Events    │ every 6 h     │ 10-min stagger

NOTE: APScheduler is used here for simplicity. When scaled beyond a single
instance, replace with a dedicated worker (ARQ, Celery, etc.) to avoid
duplicate job execution across replicas.
"""
from __future__ import annotations

import asyncio
import random
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import structlog

from voucherbot.config.settings import settings
from voucherbot.database.connection import AsyncSessionLocal
from voucherbot.models.source import SourceType
from voucherbot.providers.reddit.client import RedditClient
from voucherbot.providers.reddit.collector import RedditCollector
from voucherbot.providers.rss.collector import RssCollector
from voucherbot.providers.website.collector import WebsiteCollector
from voucherbot.services.ingestion.pipeline import run_pipeline

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------
scheduler = AsyncIOScheduler()
_reddit_client = RedditClient()

_collectors = {
    "reddit": RedditCollector(_reddit_client),
    "rss": RssCollector(),
    "web": WebsiteCollector(),
}

# Global asyncio lock — only one pipeline job runs at a time.
# This is the primary defence against OOM under low-CPU/low-RAM budgets.
_pipeline_lock = asyncio.Lock()


# ---------------------------------------------------------------------------
# Jitter helper
# ---------------------------------------------------------------------------
def _jitter() -> int:
    """Return a random ±60-second offset to spread load across ticks."""
    return random.randint(-60, 60)


# ---------------------------------------------------------------------------
# Job runners
# ---------------------------------------------------------------------------
async def _run(source_type: SourceType, fetch_limit: int = 50) -> None:
    """Acquire the global lock then run the pipeline for *source_type*."""
    if _pipeline_lock.locked():
        logger.warning(
            "scheduler: pipeline busy — skipping tick",
            source_type=source_type.value,
        )
        return

    async with _pipeline_lock:
        async with AsyncSessionLocal() as session:
            await run_pipeline(
                session, source_type, _collectors, fetch_limit=fetch_limit
            )


async def sync_reddit() -> None:
    await _run(SourceType.REDDIT, fetch_limit=settings.reddit_fetch_limit)


async def sync_rss() -> None:
    await _run(SourceType.RSS)


async def sync_blogs() -> None:
    await _run(SourceType.BLOG)


async def sync_forums() -> None:
    await _run(SourceType.FORUM)


async def sync_websites() -> None:
    await _run(SourceType.WEBSITE)


async def sync_events() -> None:
    await _run(SourceType.EVENT)


# ---------------------------------------------------------------------------
# Scheduler lifecycle
# ---------------------------------------------------------------------------
def _stagger(seconds: int) -> datetime:
    """Return an absolute start time *seconds* after now (UTC)."""
    return datetime.now(timezone.utc) + timedelta(seconds=seconds)


def start_scheduler() -> None:
    """Register all jobs and start the APScheduler event loop."""
    logger.info("scheduler: starting — conflict-free mode")

    common = dict(
        replace_existing=True,
        max_instances=1,          # never stack; skip if previous run is still active
        misfire_grace_time=120,   # if a tick fires >2 min late, treat it as missed (skip)
        coalesce=True,            # collapse multiple missed ticks into one
    )

    # Reddit — every 15 min, fire first after the process has fully started
    scheduler.add_job(
        sync_reddit,
        IntervalTrigger(minutes=15, jitter=60, start_date=_stagger(0)),
        id="sync_reddit",
        **common,
    )

    # RSS — every 30 min, start 2 min after Reddit's first run
    scheduler.add_job(
        sync_rss,
        IntervalTrigger(minutes=30, jitter=60, start_date=_stagger(120)),
        id="sync_rss",
        **common,
    )

    # Blogs — every 60 min, start 4 min in
    scheduler.add_job(
        sync_blogs,
        IntervalTrigger(hours=1, jitter=60, start_date=_stagger(240)),
        id="sync_blogs",
        **common,
    )

    # Forums — every 2 h, start 6 min in
    scheduler.add_job(
        sync_forums,
        IntervalTrigger(hours=2, jitter=60, start_date=_stagger(360)),
        id="sync_forums",
        **common,
    )

    # Vendor/aggregator websites — every 6 h, start 8 min in
    scheduler.add_job(
        sync_websites,
        IntervalTrigger(hours=6, jitter=60, start_date=_stagger(480)),
        id="sync_websites",
        **common,
    )

    # Vendor event pages — every 6 h, start 10 min in
    scheduler.add_job(
        sync_events,
        IntervalTrigger(hours=6, jitter=60, start_date=_stagger(600)),
        id="sync_events",
        **common,
    )

    scheduler.start()
    logger.info("scheduler: all jobs registered", total_jobs=len(scheduler.get_jobs()))


async def stop_scheduler() -> None:
    """Gracefully stop the scheduler and close the Reddit client."""
    logger.info("scheduler: shutting down")
    scheduler.shutdown(wait=False)
    await _reddit_client.close()
