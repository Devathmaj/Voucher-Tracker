import asyncio
import os
import sys

# Add the project root to the python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.dialects.postgresql import insert
from voucherbot.models.source import Source, SourceType
from voucherbot.config.settings import settings

sources = [
    {
        "name": "MSFT Hub Vouchers",
        "type": SourceType.WEBSITE,
        "base_url": "https://msfthub.com/",
        "config": {
            "url": "https://msfthub.com/vouchers/",
            "article_selector": "li",
            "title_selector": "span",
            "link_selector": "a"
        }
    },
    {
        "name": "AWS Builder",
        "type": SourceType.RSS,
        "base_url": "https://builder.aws.com/",
        "config": {"feed_url": "https://builder.aws.com/rss.xml"}
    },
    {
        "name": "Microsoft Blogs",
        "type": SourceType.RSS,
        "base_url": "https://blogs.microsoft.com/",
        "config": {"feed_url": "https://blogs.microsoft.com/feed/"}
    },
    {
        "name": "Microsoft Learn Blog",
        "type": SourceType.RSS,
        "base_url": "https://techcommunity.microsoft.com/t5/microsoft-learn-blog/bg-p/MicrosoftLearnBlog",
        "config": {"feed_url": "https://techcommunity.microsoft.com/t5/microsoft-learn-blog/bg-p/MicrosoftLearnBlog/rss"}
    },
    {
        "name": "Linux.com",
        "type": SourceType.RSS,
        "base_url": "https://www.linux.com/",
        "config": {"feed_url": "https://www.linux.com/feed/"}
    },
    {
        "name": "TechExams",
        "type": SourceType.RSS,
        "base_url": "https://community.techexams.net/",
        "config": {"feed_url": "https://community.techexams.net/discussions/feed.rss"}
    },
    {
        "name": "InfoSec Institute",
        "type": SourceType.RSS,
        "base_url": "https://community.infosecinstitute.com/",
        "config": {"feed_url": "https://community.infosecinstitute.com/discussions/feed.rss"}
    }
]

async def bootstrap():
    engine = create_async_engine(settings.database_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    async with async_session() as session:
        print("Inserting sources...")
        for src in sources:
            stmt = insert(Source).values(
                name=src["name"],
                type=src["type"],
                base_url=src["base_url"],
                config=src["config"],
                enabled=True,
                priority=1
            ).on_conflict_do_nothing(index_elements=['name'])
            await session.execute(stmt)
            
        await session.commit()
        print("Bootstrap of sources complete!")

if __name__ == "__main__":
    asyncio.run(bootstrap())
