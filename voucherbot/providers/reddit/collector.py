from datetime import datetime, timezone
from typing import Any
import structlog

from voucherbot.providers.base import BaseCollector, NormalizedPost
from voucherbot.providers.reddit.client import RedditClient

logger = structlog.get_logger(__name__)


class RedditCollector(BaseCollector):
    """Collects posts from a subreddit via asyncpraw."""

    def __init__(self, client: RedditClient) -> None:
        self.client = client

    async def collect(self, source_config: dict[str, Any], limit: int = 25) -> list[NormalizedPost]:
        subreddit_name = source_config.get("subreddit", "")
        if not subreddit_name:
            logger.warning("RedditCollector: no subreddit in config", config=source_config)
            return []

        raw_posts = await self.client.fetch_new_posts(subreddit_name, limit=limit)
        results: list[NormalizedPost] = []

        for post in raw_posts:
            author_name = "[deleted]"
            if post.author:
                try:
                    author_name = post.author.name
                except Exception:
                    pass

            results.append(NormalizedPost(
                external_id=post.id,
                url=f"https://www.reddit.com{post.permalink}",
                title=post.title,
                content=post.selftext or None,
                summary=None,
                author=author_name,
                published_at=datetime.fromtimestamp(post.created_utc, tz=timezone.utc),
                raw_data={
                    "score": post.score,
                    "num_comments": post.num_comments,
                    "url": post.url,
                    "subreddit": subreddit_name,
                    "flair": post.link_flair_text,
                }
            ))

        return results
