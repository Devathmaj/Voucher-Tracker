import asyncio
import sys
import os
import structlog
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from voucherbot.config.settings import settings
from voucherbot.database.connection import AsyncSessionLocal
from voucherbot.models.source import Source, SourceType
from voucherbot.models.keyword import Keyword
from voucherbot.services.ingestion.pipeline import run_pipeline
from voucherbot.providers.rss.collector import RssCollector
from voucherbot.providers.reddit.collector import RedditCollector

async def main():
    print("=" * 60)
    print("  VoucherBot - Live Pipeline Test")
    print("=" * 60)

    # 1. Setup test source (AWS RSS feed) and keyword
    async with AsyncSessionLocal() as session:
        # Enable some keywords
        await session.execute(
            insert(Keyword).values(keyword="cert", score=1, enabled=True)
            .on_conflict_do_nothing()
        )
        
        # Add test RSS source
        source_name = "AWS Builder (Test)"
        await session.execute(
            insert(Source).values(
                name=source_name,
                type=SourceType.RSS,
                base_url="https://builder.aws.com/",
                config={"feed_url": "https://builder.aws.com/rss.xml"},
                enabled=True,
                priority=1
            ).on_conflict_do_nothing(index_elements=['name'])
        )
        await session.commit()
        
        # Reset last_checked so it runs immediately
        source = (await session.execute(select(Source).where(Source.name == source_name))).scalar_one_or_none()
        if source:
            source.last_checked_utc = None
            await session.commit()

    print("\n[INFO] Set up test keywords and source. Triggering pipeline...")
    
    # 2. Run pipeline
    collectors = {
        "rss": RssCollector(),
    }
    
    async with AsyncSessionLocal() as session:
        # This will run the pipeline for all enabled RSS sources
        stats = await run_pipeline(session, SourceType.RSS, collectors, fetch_limit=10)
        
    print("\n" + "=" * 60)
    print("  Pipeline Execution Complete")
    print("=" * 60)
    print(f"Stats:")
    for k, v in stats.items():
        print(f"  {k}: {v}")

if __name__ == "__main__":
    # Ensure logs output to console
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer()
        ]
    )
    asyncio.run(main())
