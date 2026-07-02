"""Background scheduler: continuous self-rescheduling loop.

Each tick runs immediately after the previous one finishes — no fixed interval.
The DB lease (pipeline_lock) ensures only one tick runs at a time across
processes. Between ticks a short idle sleep prevents busy-looping when all
sources are up to date.
"""
from __future__ import annotations

import asyncio
import uuid

import structlog

from voucherbot.database.connection import AsyncSessionLocal
from voucherbot.providers.reddit.client import RedditClient
from voucherbot.providers.reddit.collector import RedditCollector
from voucherbot.providers.rss.collector import RssCollector
from voucherbot.providers.website.collector import WebsiteCollector
from voucherbot.services.dispatcher import dispatch_tick

logger = structlog.get_logger(__name__)

_reddit_client = RedditClient()
_collectors = {
    "reddit": RedditCollector(_reddit_client),
    "rss": RssCollector(),
    "web": WebsiteCollector(),
}

_loop_task: asyncio.Task | None = None

# Seconds to wait before next tick when all sources are idle or busy.
_IDLE_SLEEP = 30
_BUSY_SLEEP = 5


async def _run_loop() -> None:
    logger.info("scheduler: loop started")
    while True:
        holder_id = str(uuid.uuid4())[:8]
        try:
            async with AsyncSessionLocal() as session:
                result = await dispatch_tick(session, _collectors, holder_id)
            status = result.get("status")
            logger.info("scheduler: tick complete", **result)
            if status in ("idle", "busy"):
                # No work done — wait before checking again to avoid hammering DB.
                sleep = _IDLE_SLEEP if status == "idle" else _BUSY_SLEEP
                await asyncio.sleep(sleep)
            # status == "ran" or "failed": proceed immediately to next source.
        except asyncio.CancelledError:
            logger.info("scheduler: loop cancelled")
            return
        except Exception as exc:
            logger.error("scheduler: unexpected loop error", error=str(exc))
            await asyncio.sleep(_IDLE_SLEEP)


def start_scheduler() -> None:
    global _loop_task
    logger.info("scheduler: starting loop")
    _loop_task = asyncio.ensure_future(_run_loop())


async def stop_scheduler() -> None:
    global _loop_task
    logger.info("scheduler: shutting down")
    if _loop_task and not _loop_task.done():
        _loop_task.cancel()
        await asyncio.gather(_loop_task, return_exceptions=True)
    await _reddit_client.close()
