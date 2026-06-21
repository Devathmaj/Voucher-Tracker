from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
import structlog
import feedparser
import hashlib

from voucherbot.providers.base import BaseCollector, NormalizedPost

logger = structlog.get_logger(__name__)


def _parse_date(entry) -> datetime | None:
    """Parse a date from an RSS entry, trying multiple fields."""
    for attr in ("published_parsed", "updated_parsed"):
        val = getattr(entry, attr, None)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return None


class RssCollector(BaseCollector):
    """Collects items from an RSS/Atom feed."""

    async def collect(self, source_config: dict[str, Any], limit: int = 50) -> list[NormalizedPost]:
        feed_url = source_config.get("feed_url", "")
        if not feed_url:
            logger.warning("RssCollector: no feed_url in config", config=source_config)
            return []

        logger.info("RssCollector: fetching", feed_url=feed_url)
        # feedparser is sync — fine for now as it's not blocking the event loop long
        feed = feedparser.parse(feed_url)

        if feed.bozo and not feed.entries:
            logger.error("RssCollector: failed to parse feed", feed_url=feed_url, error=str(feed.bozo_exception))
            return []

        results: list[NormalizedPost] = []
        for entry in feed.entries[:limit]:
            url = entry.get("link", "")
            # Use the GUID if present, otherwise hash the URL as a stable ID
            external_id = entry.get("id") or hashlib.sha1(url.encode()).hexdigest()
            content = entry.get("summary") or entry.get("description") or None

            results.append(NormalizedPost(
                external_id=external_id,
                url=url,
                title=entry.get("title", "(no title)"),
                content=content,
                summary=None,
                author=entry.get("author"),
                published_at=_parse_date(entry),
                raw_data={"feed_url": feed_url, "tags": [t.term for t in entry.get("tags", [])]},
            ))

        logger.info("RssCollector: collected", feed_url=feed_url, count=len(results))
        return results
