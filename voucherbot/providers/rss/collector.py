from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
import json
import re
import structlog
import httpx
from lxml import etree
import feedparser
import hashlib
from bs4 import BeautifulSoup

from voucherbot.providers.base import BaseCollector, NormalizedPost

logger = structlog.get_logger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/rss+xml, application/atom+xml, application/xml, application/json, text/xml, */*",
}

# Legacy Tech Community blog URLs redirect to login; map them to working syndication endpoints.
_TECHCOMMUNITY_FEED_REWRITES: dict[str, str] = {
    "https://techcommunity.microsoft.com/t5/microsoft-learn-blog/bg-p/MicrosoftLearnBlog/rss": (
        "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/Community"
        "?interaction.style=blog&labels=Microsoft+Learn+Blog"
    ),
}

# cloud.google.com/blog/rss now serves HTML; the Atom feed moved to cloudblog.withgoogle.com.
_GOOGLE_CLOUD_BLOG_RE = re.compile(
    r"^https://cloud\.google\.com/blog/rss/?$",
    re.IGNORECASE,
)


def _normalize_feed_url(feed_url: str) -> str:
    """Rewrite known-broken feed URLs while leaving custom configs untouched."""
    if feed_url in _TECHCOMMUNITY_FEED_REWRITES:
        return _TECHCOMMUNITY_FEED_REWRITES[feed_url]

    if _GOOGLE_CLOUD_BLOG_RE.match(feed_url):
        return "https://cloudblog.withgoogle.com/rss/"

    if (
        "techcommunity.microsoft.com" in feed_url
        and "/rss" in feed_url
        and "/t5/s/" not in feed_url
        and "gxcuf89792" in feed_url
    ):
        return feed_url.replace(
            "techcommunity.microsoft.com/",
            "techcommunity.microsoft.com/t5/s/",
            1,
        )

    return feed_url


def _looks_like_html(content: bytes) -> bool:
    start = content.lstrip()[:256].lower()
    return start.startswith(b"<!doctype html") or start.startswith(b"<html")


def _clean_html(value: Any) -> str | None:
    if not value or not isinstance(value, str):
        return None
    return BeautifulSoup(value, "lxml").get_text(separator=" ", strip=True) or None


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


def _parse_json_date(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


class RssCollector(BaseCollector):
    """Collects items from an RSS/Atom feed."""

    async def collect(self, source_config: dict[str, Any], limit: int = 50) -> list[NormalizedPost]:
        if source_config.get("unsupported"):
            logger.info(
                "RssCollector: source marked unsupported",
                reason=source_config.get("unsupported_reason"),
            )
            return []

        feed_url = _normalize_feed_url(source_config.get("feed_url", ""))
        if not feed_url:
            logger.warning("RssCollector: no feed_url in config", config=source_config)
            return []

        timeout = float(source_config.get("timeout_seconds", 15))
        logger.info("RssCollector: fetching", feed_url=feed_url)

        try:
            async with httpx.AsyncClient(
                headers=HEADERS,
                follow_redirects=True,
                timeout=timeout,
            ) as client:
                r = await client.get(feed_url)
                r.raise_for_status()
                content = r.content
        except Exception as e:
            logger.error("RssCollector: HTTP error", feed_url=feed_url, error=str(e))
            return []

        if _looks_like_html(content):
            logger.error(
                "RssCollector: feed URL returned HTML instead of XML/JSON",
                feed_url=feed_url,
            )
            return []

        json_results = self._parse_json_feed(content, source_config, limit)
        if json_results:
            logger.info("RssCollector: collected JSON feed", feed_url=feed_url, count=len(json_results))
            return json_results

        feed = feedparser.parse(content)

        if feed.bozo and not feed.entries:
            logger.warning("RssCollector: standard parse failed, attempting lxml recovery", feed_url=feed_url)
            try:
                parser = etree.XMLParser(recover=True)
                root = etree.fromstring(content, parser)
                if root is None:
                    raise ValueError("XML parser returned no root element")
                repaired_xml = etree.tostring(root, encoding="unicode")
                feed = feedparser.parse(repaired_xml)
            except Exception as e:
                logger.error("RssCollector: recovery failed", feed_url=feed_url, error=str(e))
                return []

        if feed.bozo and not feed.entries:
            logger.error(
                "RssCollector: failed to parse feed even after recovery",
                feed_url=feed_url,
                error=str(feed.bozo_exception),
            )
            return []

        results: list[NormalizedPost] = []
        for entry in feed.entries[:limit]:
            url = entry.get("link", "")
            external_id = entry.get("id") or hashlib.sha1(url.encode()).hexdigest()
            content_text = _clean_html(entry.get("summary") or entry.get("description"))

            results.append(NormalizedPost(
                external_id=external_id,
                url=url,
                title=entry.get("title", "(no title)"),
                content=content_text,
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
            summary = _clean_html(item.get("summary"))
            content_text = _clean_html(item.get("summary") or item.get("description") or item.get("body"))
            published_at = _parse_json_date(
                item.get("publishedDate") or item.get("pubDate") or item.get("date")
            )

            results.append(
                NormalizedPost(
                    external_id=external_id,
                    url=url or feed_url,
                    title=title,
                    content=content_text,
                    summary=summary,
                    author=item.get("author"),
                    published_at=published_at,
                    raw_data={
                        "feed_url": feed_url,
                        "vendor": source_config.get("vendor"),
                        "format": "json",
                    },
                )
            )

        return results
