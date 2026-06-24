from datetime import datetime, timezone
from typing import Any
import hashlib
import httpx
import structlog
from bs4 import BeautifulSoup

from voucherbot.providers.base import BaseCollector, NormalizedPost

logger = structlog.get_logger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; VoucherBot/0.1; +https://github.com/voucherbot)"
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
        url = source_config.get("url", "")
        article_selector = source_config.get("article_selector", "article")
        title_selector = source_config.get("title_selector", "h2")
        link_selector = source_config.get("link_selector", "a")

        if not url:
            logger.warning("WebsiteCollector: no url in config", config=source_config)
            return []

        logger.info("WebsiteCollector: fetching", url=url)
        try:
            async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=15) as client:
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
            link_el = article.select_one(link_selector)

            title = title_el.get_text(strip=True) if title_el else ""
            href = link_el.get("href", "") if link_el else ""

            if not title and not href:
                continue

            # Resolve relative links
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
