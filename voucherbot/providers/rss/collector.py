from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
import json
import structlog
import httpx
from lxml import etree
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
        
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
                r = await client.get(feed_url)
                r.raise_for_status()
                content = r.content
        except Exception as e:
            logger.error("RssCollector: HTTP error", feed_url=feed_url, error=str(e))
            return []

        json_results = self._parse_json_feed(content, source_config, limit)
        if json_results:
            logger.info("RssCollector: collected JSON feed", feed_url=feed_url, count=len(json_results))
            return json_results

        # Try to parse with feedparser directly first
        feed = feedparser.parse(content)

        if feed.bozo and not feed.entries:
            logger.warning("RssCollector: standard parse failed, attempting lxml recovery", feed_url=feed_url)
            try:
                parser = etree.XMLParser(recover=True)
                root = etree.fromstring(content, parser)
                repaired_xml = etree.tostring(root)
                feed = feedparser.parse(repaired_xml)
            except Exception as e:
                logger.error("RssCollector: recovery failed", feed_url=feed_url, error=str(e))
                return []

        if feed.bozo and not feed.entries:
            logger.error("RssCollector: failed to parse feed even after recovery", feed_url=feed_url, error=str(feed.bozo_exception))
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
                raw_data={
                    "feed_url": feed_url,
                    "vendor": source_config.get("vendor"),
                    "tags": [t.term for t in entry.get("tags", [])],
                },
            ))

        logger.info("RssCollector: collected", feed_url=feed_url, count=len(results))
        return results

    def _parse_json_feed(
        self,
        content: bytes,
        source_config: dict[str, Any],
        limit: int,
    ) -> list[NormalizedPost]:
        try:
            payload = json.loads(content)
        except Exception:
            return []

        feed_url = source_config.get("feed_url", "")
        items = payload.get("items") or payload.get("articles") or payload.get("data") or []
        if not isinstance(items, list):
            return []

        results: list[NormalizedPost] = []
        for item in items[:limit]:
            if not isinstance(item, dict):
                continue

            url = item.get("url") or item.get("link") or item.get("canonicalUrl") or ""
            title = item.get("title") or item.get("headline") or item.get("name") or "(no title)"
            external_id = str(item.get("id") or item.get("guid") or hashlib.sha1(url.encode()).hexdigest())
            content_text = item.get("summary") or item.get("description") or item.get("body")

            results.append(
                NormalizedPost(
                    external_id=external_id,
                    url=url or feed_url,
                    title=title,
                    content=content_text,
                    summary=item.get("summary"),
                    author=item.get("author"),
                    published_at=None,
                    raw_data={
                        "feed_url": feed_url,
                        "vendor": source_config.get("vendor"),
                        "format": "json",
                    },
                )
            )

        return results
