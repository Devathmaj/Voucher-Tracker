from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import structlog
from voucherbot.config.settings import settings
from voucherbot.database.init_db import async_session_maker
from voucherbot.providers.reddit.client import RedditClient
from voucherbot.services.ingestion.reddit_sync import sync_all_subreddits

logger = structlog.get_logger(__name__)

# Global instances
scheduler = AsyncIOScheduler()
reddit_client = RedditClient()

async def scheduled_reddit_sync():
    """Job function to run the reddit sync."""
    logger.info("Triggering scheduled Reddit sync")
    async with async_session_maker() as session:
        await sync_all_subreddits(session, reddit_client)

def start_scheduler():
    logger.info("Starting APScheduler")
    # Note: APScheduler is used temporarily. Once the project is containerized 
    # or scaled beyond a single instance, replace it with a dedicated worker 
    # (ARQ, Celery, or another external scheduler).
    scheduler.add_job(
        scheduled_reddit_sync,
        trigger=IntervalTrigger(minutes=settings.reddit_fetch_interval_minutes),
        id="reddit_sync_job",
        replace_existing=True
    )
    scheduler.start()

async def stop_scheduler():
    logger.info("Stopping APScheduler")
    scheduler.shutdown(wait=False)
    await reddit_client.close()
