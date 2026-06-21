import asyncio
import uuid
from datetime import datetime, timezone
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from voucherbot.models.reddit import Subreddit, RedditKeyword, RedditPost, PostStatus
from voucherbot.providers.reddit.client import RedditClient
from voucherbot.config.settings import settings

logger = structlog.get_logger(__name__)

async def sync_all_subreddits(db: AsyncSession, reddit_client: RedditClient):
    sync_id = f"Sync #{str(uuid.uuid4())[:8]}"
    
    # Get enabled subreddits
    result = await db.execute(select(Subreddit).where(Subreddit.enabled == True))
    subreddits = result.scalars().all()
    
    # Get keywords for filtering
    kw_result = await db.execute(select(RedditKeyword).where(RedditKeyword.enabled == True))
    keywords = [kw.keyword.lower() for kw in kw_result.scalars().all()]
    
    logger.info(f"{sync_id} Starting. {len(subreddits)} subs enabled.")
    
    semaphore = asyncio.Semaphore(settings.reddit_concurrency_limit)
    
    stats = {
        "posts_fetched": 0,
        "duplicates_skipped": 0,
        "keyword_matches": 0,
        "errors": 0
    }
    
    start_time = datetime.now(timezone.utc)
    
    async def process_sub(subreddit: Subreddit):
        async with semaphore:
            try:
                sub_stats = await sync_subreddit(db, reddit_client, subreddit, keywords)
                for k, v in sub_stats.items():
                    stats[k] += v
            except Exception as e:
                logger.error(f"{sync_id} Error processing {subreddit.name}", error=str(e))
                stats["errors"] += 1

    tasks = [process_sub(sub) for sub in subreddits]
    if tasks:
        await asyncio.gather(*tasks)
    
    duration = (datetime.now(timezone.utc) - start_time).total_seconds()
    
    logger.info(
        f"{sync_id} Complete", 
        duration=f"{duration:.1f}s",
        **stats
    )

async def sync_subreddit(db: AsyncSession, reddit_client: RedditClient, subreddit: Subreddit, keywords: list[str]) -> dict:
    stats = {
        "posts_fetched": 0,
        "duplicates_skipped": 0,
        "keyword_matches": 0,
    }
    
    last_checked = subreddit.last_checked_utc
    posts = await reddit_client.fetch_new_posts(subreddit.name, limit=settings.reddit_fetch_limit)
    stats["posts_fetched"] = len(posts)
    
    for post in posts:
        post_created_utc = datetime.fromtimestamp(post.created_utc, tz=timezone.utc)
        
        if last_checked and post_created_utc <= last_checked:
            # We've reached already processed posts
            break
            
        is_match = False
        text_content = f"{post.title} {post.selftext}".lower()
        if not keywords:
            is_match = True # If no keywords, everything matches
        
        for kw in keywords:
            if kw in text_content:
                is_match = True
                break
                
        status = PostStatus.QUEUED if is_match else PostStatus.FILTERED
        if is_match:
            stats["keyword_matches"] += 1
            
        stmt = insert(RedditPost).values(
            id=post.id,
            subreddit_id=subreddit.id,
            title=post.title,
            body=post.selftext,
            url=post.url,
            permalink=post.permalink,
            author=post.author.name if post.author else "[deleted]",
            author_id=getattr(post.author, 'id', None) if post.author else None,
            is_mod=post.distinguished == 'moderator',
            distinguished=post.distinguished,
            score=post.score,
            num_comments=post.num_comments,
            created_utc=post_created_utc,
            edited_utc=datetime.fromtimestamp(post.edited, tz=timezone.utc) if getattr(post, 'edited', False) else None,
            status=status
        ).on_conflict_do_nothing(index_elements=['id'])
        
        result = await db.execute(stmt)
        if result.rowcount == 0:
            stats["duplicates_skipped"] += 1

    subreddit.last_checked_utc = datetime.now(timezone.utc)
    await db.commit()
    
    return stats
