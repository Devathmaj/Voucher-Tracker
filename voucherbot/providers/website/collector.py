from datetime import datetime, timezone
from typing import Any
import hashlib
import httpx
import structlog
from bs4 import BeautifulSoup

from voucherbot.providers.base import BaseCollector, NormalizedPost

logger = structlog.get_logger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": USER_AGENT
}


class WebsiteCollector(BaseCollector):
    """Scrapes an HTML page using configurable CSS selectors from source config.

    Expected source config shape:
    {
        "article_selector": ".news-card",   # wraps each article
        "title_selector": "h2",             # inside the article
        "link_selector": "a"                # inside the article, for href
    }
    """

    async def collect(self, source_config: dict[str, Any], limit: int = 50) -> list[NormalizedPost]:
        if source_config.get("unsupported"):
            logger.info(
                "WebsiteCollector: source marked unsupported",
                reason=source_config.get("unsupported_reason"),
            )
            return []

        url = source_config.get("url", "")
        article_selector = source_config.get("article_selector", "article")
        title_selector = source_config.get("title_selector", "h2")
        link_selector = source_config.get("link_selector", "a")

        if not url:
            logger.warning("WebsiteCollector: no url in config", config=source_config)
            return []

        timeout = float(source_config.get("timeout_seconds", 15))
        logger.info("WebsiteCollector: fetching", url=url)
        try:
            async with httpx.AsyncClient(
                headers=HEADERS,
                follow_redirects=True,
                timeout=timeout,
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
        except Exception as e:
            logger.error("WebsiteCollector: HTTP error", url=url, error=str(e))
            return []

        soup = BeautifulSoup(response.text, "lxml")
        articles = soup.select(article_selector)[:limit]
        if not articles:
            articles = [soup]

        results: list[NormalizedPost] = []
        for article in articles:
            title_el = article.select_one(title_selector)
            link_el = article if link_selector == "self" else article.select_one(link_selector)

            title = title_el.get_text(strip=True) if title_el else ""
            if not title:
                title = article.get_text(separator=" ", strip=True)
            href = link_el.get("href", "") if link_el else ""

            if not title and not href:
                continue

            if href and not href.startswith("http"):
                from urllib.parse import urljoin
                href = urljoin(url, href)

            external_id = hashlib.sha1(f"{url}:{href}:{title}".encode()).hexdigest()

            results.append(NormalizedPost(
                external_id=external_id,
                url=href or url,
                title=title or href,
                content=article.get_text(separator=" ", strip=True) or None,
                summary=None,
                author=None,
                published_at=None,
                raw_data={
                    "scraped_from": url,
                    "article_selector": article_selector,
                    "vendor": source_config.get("vendor"),
                },
            ))

        logger.info("WebsiteCollector: collected", url=url, count=len(results))
        return results
