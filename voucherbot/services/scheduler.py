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

# One shared instance per provider type
_reddit_collector = RedditCollector(_reddit_client)
_rss_collector = RssCollector()
_web_collector = WebsiteCollector()


async def _run(source_type: SourceType, collector, fetch_limit: int):
    async with AsyncSessionLocal() as session:
        await run_pipeline(session, source_type, collector, fetch_limit=fetch_limit)


async def scheduled_reddit_sync():
    logger.info("Scheduler: triggering Reddit sync")
    await _run(SourceType.REDDIT, _reddit_collector, fetch_limit=settings.reddit_fetch_limit)


async def scheduled_rss_sync():
    logger.info("Scheduler: triggering RSS sync")
    await _run(SourceType.RSS, _rss_collector, fetch_limit=50)


async def scheduled_web_sync():
    logger.info("Scheduler: triggering Website sync")
    await _run(SourceType.WEBSITE, _web_collector, fetch_limit=50)


def start_scheduler():
    logger.info("Starting scheduler")
    scheduler.add_job(scheduled_reddit_sync, IntervalTrigger(minutes=15), id="reddit_sync", replace_existing=True)
    scheduler.add_job(scheduled_rss_sync,    IntervalTrigger(minutes=30), id="rss_sync",    replace_existing=True)
    scheduler.add_job(scheduled_web_sync,    IntervalTrigger(hours=6),    id="web_sync",    replace_existing=True)
    scheduler.start()


async def stop_scheduler():
    logger.info("Stopping scheduler")
    scheduler.shutdown(wait=False)
    await _reddit_client.close()
