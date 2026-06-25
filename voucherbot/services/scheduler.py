"""
Background scheduler — DB-driven single heartbeat.

A single 2-minute APScheduler job calls the dispatcher in-process. Postgres
owns queue ordering (next_due_at, priority_tier) and concurrency (pipeline_lock).
"""
from __future__ import annotations

import uuid

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import structlog

from voucherbot.database.connection import AsyncSessionLocal
from voucherbot.providers.reddit.client import RedditClient
from voucherbot.providers.reddit.collector import RedditCollector
from voucherbot.providers.rss.collector import RssCollector
from voucherbot.providers.website.collector import WebsiteCollector
from voucherbot.config.settings import settings
from voucherbot.services.dispatcher import dispatch_tick

logger = structlog.get_logger(__name__)

scheduler = AsyncIOScheduler()
_reddit_client = RedditClient()

_collectors = {
    "reddit": RedditCollector(_reddit_client),
    "rss": RssCollector(),
    "web": WebsiteCollector(),
}


async def tick() -> None:
    """Single heartbeat — dispatch one source per call."""
    holder_id = str(uuid.uuid4())[:8]
    async with AsyncSessionLocal() as session:
        result = await dispatch_tick(session, _collectors, holder_id)
    logger.info("scheduler: tick complete", **result)


def start_scheduler() -> None:
    """Register the heartbeat job and start APScheduler."""
    logger.info(
        "scheduler: starting — DB-driven mode",
        reddit_ingestion_enabled=settings.reddit_ingestion_enabled,
    )

    scheduler.add_job(
        tick,
        IntervalTrigger(minutes=2, jitter=30),
        id="heartbeat_tick",
        max_instances=1,
        misfire_grace_time=120,
        coalesce=True,
        replace_existing=True,
    )

    scheduler.start()
    logger.info("scheduler: heartbeat registered")


async def stop_scheduler() -> None:
    """Gracefully stop the scheduler and close the Reddit client."""
    logger.info("scheduler: shutting down")
    scheduler.shutdown(wait=False)
    await _reddit_client.close()
