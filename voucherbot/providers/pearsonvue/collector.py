from typing import Any
import asyncio
import hashlib
import structlog
from bs4 import BeautifulSoup

from voucherbot.providers.base import BaseCollector, NormalizedPost
from voucherbot.providers.http_policy import polite_get, RobotsDisallowedError

logger = structlog.get_logger(__name__)


class PearsonVUECollector(BaseCollector):
    """Scrapes Pearson VUE vendor program pages.

    Returns one NormalizedPost per slider/promotion item found on the page
    (via data-slide-url-title + data-slide-url attributes), plus one post
    for the general page content.
    """

    async def collect(
        self, source_config: dict[str, Any], limit: int = 50
    ) -> list[NormalizedPost]:
        if source_config.get("unsupported"):
            logger.info(
                "PearsonVUECollector: source marked unsupported",
                reason=source_config.get("unsupported_reason"),
            )
            return []

        url = source_config.get("url", "")
        vendor = source_config.get("vendor", "")

        if not url:
            logger.warning(
                "PearsonVUECollector: no url in config", config=source_config
            )
            return []

        timeout = float(source_config.get("timeout_seconds", 15))
        logger.info("PearsonVUECollector: fetching", url=url, vendor=vendor)

        try:
            response = await polite_get(
                url,
                accept="text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
                timeout=timeout,
            )
        except RobotsDisallowedError:
            logger.info("PearsonVUECollector: skipped (robots.txt)", url=url)
            return []
        except Exception as e:
            logger.error(
                "PearsonVUECollector: HTTP error", url=url, vendor=vendor, error=str(e)
            )
            return []

        soup = await asyncio.to_thread(BeautifulSoup, response.text, "html.parser")

        for tag in soup.select("nav, footer, .cookie-banner, script, style"):
            tag.decompose()

        main = soup.find("main") or soup.find("body")
        if main is None:
            logger.warning("PearsonVUECollector: no main content found", url=url)
            return []

        # ── Extract slider promotion items (individual posts) ─────────────
        seen_urls: set[str] = set()
        results: list[NormalizedPost] = []

        for el in soup.find_all(lambda tag: tag.has_attr("data-slide-url-title")):
            slide_title = el["data-slide-url-title"]
            slide_url = el.get("data-slide-url", "")

            if not slide_title:
                continue

            full_url = slide_url
            if full_url and not full_url.startswith("http"):
                from urllib.parse import urljoin
                full_url = urljoin(url, full_url)

            dedup_key = full_url or slide_title
            if dedup_key in seen_urls:
                continue
            seen_urls.add(dedup_key)

            slide_text = el.get_text(separator=" ", strip=True)

            external_id = hashlib.sha256(
                f"pearsonvue-{vendor}-{slide_title}".encode()
            ).hexdigest()[:32]

            content_parts = [slide_title]
            if slide_text and slide_text != slide_title:
                content_parts.append(slide_text)

            results.append(
                NormalizedPost(
                    external_id=external_id,
                    url=full_url or url,
                    title=slide_title,
                    content="\n".join(content_parts),
                    raw_data={
                        "scraped_from": url,
                        "vendor": vendor,
                        "type": "slide_promo",
                    },
                )
            )

        for el in soup.find_all(lambda tag: tag.has_attr("data-slide-url")):
            slide_url = el["data-slide-url"]
            slide_text = el.get_text(separator=" ", strip=True)
            if slide_url and slide_url not in seen_urls:
                seen_urls.add(slide_url)

                full_url = slide_url
                if not full_url.startswith("http"):
                    from urllib.parse import urljoin
                    full_url = urljoin(url, full_url)

                external_id = hashlib.sha256(
                    f"pearsonvue-{vendor}-slide-{slide_url}".encode()
                ).hexdigest()[:32]

                results.append(
                    NormalizedPost(
                        external_id=external_id,
                        url=full_url,
                        title=slide_text or f"Promotion from {vendor}",
                        content=slide_text or "",
                        raw_data={
                            "scraped_from": url,
                            "vendor": vendor,
                            "type": "slide_link",
                        },
                    )
                )

        # ── General page content as fallback ──────────────────────────────
        sections = []
        current_heading = None

        for el in main.find_all(["h1", "h2", "h3", "h4", "p", "li", "a"]):
            tag = el.name
            text = el.get_text(separator=" ", strip=True)
            if not text or len(text) < 5:
                continue
            if tag in ("h1", "h2", "h3", "h4"):
                current_heading = text
            else:
                entry: dict[str, Any] = {
                    "heading": current_heading,
                    "type": tag,
                    "text": text,
                }
                if tag == "a" and el.get("href"):
                    entry["href"] = el["href"]
                sections.append(entry)

        last_updated = None
        for p in soup.find_all("p"):
            t = p.get_text(strip=True)
            if t.startswith("Last updated"):
                last_updated = t
                break

        content_parts = [f"Last updated: {last_updated}"] if last_updated else []
        for sec in sections:
            line = sec["text"]
            if sec.get("heading"):
                line = f"[{sec['heading']}] {line}"
            content_parts.append(line)

        page_external_id = hashlib.sha256(url.encode()).hexdigest()[:32]
        results.append(
            NormalizedPost(
                external_id=page_external_id,
                url=url,
                title=f"Pearson VUE — {vendor} Certification Programs",
                content="\n".join(content_parts),
                summary=f"{len(sections)} sections across {vendor} certification programs on Pearson VUE",
                raw_data={
                    "scraped_from": url,
                    "vendor": vendor,
                    "type": "page_overview",
                },
            )
        )

        logger.info(
            "PearsonVUECollector: collected",
            url=url,
            vendor=vendor,
            slide_promos=len(results) - 1,
            sections=len(sections),
        )
        return results[:limit]