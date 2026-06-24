"""
Background scheduler: triggers each provider on its own cadence.

NOTE: APScheduler is used here for simplicity. When scaled beyond a single
instance, replace with a dedicated worker (ARQ, Celery, etc.) to avoid
duplicate job execution across replicas.
"""
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

scheduler = AsyncIOScheduler()
_reddit_client = RedditClient()

# Shared instances
_collectors = {
    "reddit": RedditCollector(_reddit_client),
    "rss": RssCollector(),
    "web": WebsiteCollector(),
}


async def _run(source_type: SourceType, fetch_limit: int = 50):
    async with AsyncSessionLocal() as session:
        await run_pipeline(session, source_type, _collectors, fetch_limit=fetch_limit)


async def sync_reddit():
    await _run(SourceType.REDDIT, fetch_limit=settings.reddit_fetch_limit)

async def sync_rss():
    await _run(SourceType.RSS)

async def sync_blogs():
    await _run(SourceType.BLOG)

async def sync_forums():
    await _run(SourceType.FORUM)

async def sync_events():
    await _run(SourceType.EVENT)

async def sync_websites():
    await _run(SourceType.WEBSITE)


def start_scheduler():
    logger.info("Starting scheduler")
    
    # Reddit: 15 min
    scheduler.add_job(sync_reddit, IntervalTrigger(minutes=15), id="sync_reddit", replace_existing=True)
    
    # RSS: 30 min
    scheduler.add_job(sync_rss, IntervalTrigger(minutes=30), id="sync_rss", replace_existing=True)
    
    # Blogs: 1 hour
    scheduler.add_job(sync_blogs, IntervalTrigger(hours=1), id="sync_blogs", replace_existing=True)
    
    # Forums: 2 hours
    scheduler.add_job(sync_forums, IntervalTrigger(hours=2), id="sync_forums", replace_existing=True)
    
    # Vendor event pages: 6 hours
    scheduler.add_job(sync_events, IntervalTrigger(hours=6), id="sync_events", replace_existing=True)

    # Static vendor and aggregator pages: 6 hours, source configs decide actual cadence
    scheduler.add_job(sync_websites, IntervalTrigger(hours=6), id="sync_websites", replace_existing=True)
    
    scheduler.start()


async def stop_scheduler():
    logger.info("Stopping scheduler")
    scheduler.shutdown(wait=False)
    await _reddit_client.close()
