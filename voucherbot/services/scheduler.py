"""Background scheduler: DB-driven single heartbeat.

A single APScheduler job calls the dispatcher in-process. Postgres owns queue
ordering, source lease state, and cross-process concurrency through
``pipeline_lock``.
"""
from __future__ import annotations

import asyncio
import uuid

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import structlog

from voucherbot.config.settings import settings
from voucherbot.database.connection import AsyncSessionLocal
from voucherbot.providers.reddit.client import RedditClient
from voucherbot.providers.reddit.collector import RedditCollector
from voucherbot.providers.rss.collector import RssCollector
from voucherbot.providers.website.collector import WebsiteCollector
from voucherbot.services.dispatcher import dispatch_tick

logger = structlog.get_logger(__name__)

scheduler = AsyncIOScheduler()
_reddit_client = RedditClient()
_active_ticks: set[asyncio.Task] = set()

_collectors = {
    "reddit": RedditCollector(_reddit_client),
    "rss": RssCollector(),
    "web": WebsiteCollector(),
}


async def tick() -> None:
    """Dispatch one due source and track it for graceful shutdown."""
    task = asyncio.current_task()
    if task is not None:
        _active_ticks.add(task)

    holder_id = str(uuid.uuid4())[:8]
    try:
        async with AsyncSessionLocal() as session:
            result = await dispatch_tick(session, _collectors, holder_id)
        logger.info("scheduler: tick complete", **result)
    finally:
        if task is not None:
            _active_ticks.discard(task)


def start_scheduler() -> None:
    """Register the heartbeat job and start APScheduler."""
    logger.info(
        "scheduler: starting - DB-driven mode",
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
    """Stop scheduling new work, then wait for any running tick."""
    logger.info("scheduler: shutting down")
    scheduler.shutdown(wait=False)
    if _active_ticks:
        logger.info("scheduler: waiting for active ticks", count=len(_active_ticks))
        await asyncio.gather(*list(_active_ticks), return_exceptions=True)
    await _reddit_client.close()
