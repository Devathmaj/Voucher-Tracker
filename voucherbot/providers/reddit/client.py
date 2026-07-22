import asyncio
import asyncpraw
from asyncpraw.models import Subreddit
from asyncprawcore.exceptions import RequestException, ResponseException
import structlog
from typing import Any
from tenacity import (
    retry,
    wait_exponential,
    stop_after_attempt,
    retry_if_exception_type,
)

from voucherbot.config.settings import settings

logger = structlog.get_logger(__name__)


class RedditClient:
    def __init__(self) -> None:
        self.is_configured = bool(
            settings.reddit_client_id
            and settings.reddit_client_secret
            and settings.reddit_user_agent
        )
        self.reddit = (
            asyncpraw.Reddit(
                client_id=settings.reddit_client_id or "placeholder",
                client_secret=settings.reddit_client_secret or "placeholder",
                user_agent=settings.reddit_user_agent or "placeholder",
            )
            if self.is_configured
            else None
        )
        self.subreddit_cache: dict[str, Subreddit] = {}

    async def get_subreddit(self, name: str) -> Subreddit:
        if not self.reddit:
            raise RuntimeError("Reddit client is not configured")
        if name not in self.subreddit_cache:
            self.subreddit_cache[name] = await self.reddit.subreddit(name)
        return self.subreddit_cache[name]

    @retry(
        wait=wait_exponential(multiplier=1, min=4, max=60),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type((RequestException, ResponseException)),
        reraise=True,
    )
    async def fetch_new_posts(self, subreddit_name: str, limit: int = 25) -> list[Any]:
        """Fetch new posts from a subreddit."""
        sub = await self.get_subreddit(subreddit_name)
        posts = []
        try:
            async for post in sub.new(limit=limit):
                posts.append(post)
        except Exception as e:
            logger.error(f"Error fetching posts from {subreddit_name}", error=str(e))
            raise
        return posts

    @retry(
        wait=wait_exponential(multiplier=1, min=4, max=60),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type((RequestException, ResponseException)),
        reraise=True,
    )
    async def fetch_post_comments(self, post_id: str, limit: int = 10) -> Any:
        """Fetch comments for a specific post."""
        if not self.reddit:
            raise RuntimeError("Reddit client is not configured")
        try:
            submission = await self.reddit.submission(id=post_id)
            submission.comment_limit = limit
            await submission.load()
            return submission.comments
        except Exception as e:
            logger.error(f"Error fetching comments for post {post_id}", error=str(e))
            raise

    async def search_posts(
        self, query: str, subreddit_name: str = "all", limit: int = 25
    ) -> list[Any]:
        """Search posts."""
        sub = await self.get_subreddit(subreddit_name)
        posts = []
        try:
            async for post in sub.search(query, limit=limit):
                posts.append(post)
        except Exception as e:
            logger.error(f"Error searching posts in {subreddit_name}", error=str(e))
            raise
        return posts

    async def close(self) -> None:
        """Close the underlying HTTP session."""
        if self.reddit:
            await self.reddit.close()
