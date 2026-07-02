"""
Startup bootstrap for source and keyword seed data.

The source catalog is intentionally config-driven: collectors read the JSONB
config, so adding feeds/pages does not require a schema migration.
"""
from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert

from voucherbot.database.connection import AsyncSessionLocal
from voucherbot.models.keyword import Keyword
from voucherbot.models.source import Source, SourceType

logger = structlog.get_logger(__name__)

DEFAULT_QUERY_TERMS = [
    "voucher",
    "coupon",
    "promo code",
    "free exam",
    "exam voucher",
    "discount",
    "100% off",
    "50% off",
    "redeem",
]

KEYWORDS = [
    {"keyword": "voucher", "score": 5},
    {"keyword": "coupon", "score": 5},
    {"keyword": "100% off", "score": 5},
    {"keyword": "promo code", "score": 5},
    {"keyword": "free exam", "score": 5},
    {"keyword": "exam voucher", "score": 5},
    {"keyword": "certification voucher", "score": 5},
    {"keyword": "free certification", "score": 4},
    {"keyword": "free access", "score": 4},
    {"keyword": "discount", "score": 4},
    {"keyword": "redeem", "score": 4},
    {"keyword": "50% off", "score": 4},
    {"keyword": "retake", "score": 3},
    {"keyword": "safeguard", "score": 3},
    {"keyword": "limited time", "score": 3},
    {"keyword": "beta access", "score": 3},
    {"keyword": "free tier", "score": 3},
    {"keyword": "register now", "score": 1},
    {"keyword": "webinar", "score": 1},
    {"keyword": "virtual event", "score": 1},
    {"keyword": "virtual training", "score": 2},
    {"keyword": "free training", "score": 2},
    {"keyword": "live session", "score": 1},
    {"keyword": "certification", "score": 1},
    {"keyword": "exam", "score": 1},
    {"keyword": "pearsonvue", "score": 2},
]

HIGH_SIGNAL_REDDIT_SUBREDDITS = [
    "AWSCertifications",
    "AzureCertification",
    "MicrosoftLearn",
    "CompTIA",
    "ccna",
    "cissp",
    "isc2",
    "redhat",
    "LinuxCertifications",
    "kubernetes",
    "googlecloud",
    "OracleCloud",
    "eFreebies",
    "FREE",
    "Udemy",
    "FreeUdemyCoupons",
]

# Removed from catalog — too noisy for cert-voucher signal.
DISABLED_REDDIT_SUBREDDITS = {"deals", "freebies"}

TIER_A_REDDIT_SUBS = {
    "AWSCertifications",
    "AzureCertification",
    "eFreebies",
    "FREE",
    "Udemy",
    "FreeUdemyCoupons",
}

_TIER_CADENCE_MINUTES = {
    "A": 15,
    "B": 60,
    "C": 240,
    "D": 720,
}


def _reddit_tier(sub: str) -> str:
    return "A" if sub in TIER_A_REDDIT_SUBS else "B"


def _source_name(source_type: SourceType, label: str) -> str:
    slug = (
        label.lower()
        .replace("&", "and")
        .replace("/", "_")
        .replace(" ", "_")
        .replace(":", "")
    )
    return f"{source_type.value.lower()}:{slug}"


def _feed(
    label: str,
    feed_url: str,
    source_type: SourceType = SourceType.RSS,
    *,
    vendor: str | None = None,
    priority_tier: str = "B",
    cadence_minutes: int | None = None,
    priority: int = 1,
    query_terms: list[str] | None = None,
    note: str | None = None,
    unsupported: bool = False,
    unsupported_reason: str | None = None,
    enabled: bool | None = None,
) -> dict[str, Any]:
    interval = cadence_minutes if cadence_minutes is not None else _TIER_CADENCE_MINUTES[priority_tier]
    config: dict[str, Any] = {
        "feed_url": feed_url,
        "vendor": vendor,
        "query_terms": query_terms or DEFAULT_QUERY_TERMS,
        "poll_interval_minutes": interval,
    }
    if note:
        config["note"] = note
    if unsupported:
        config["unsupported"] = True
        config["unsupported_reason"] = unsupported_reason or "Blocked by site policy"
    return {
        "name": _source_name(source_type, label),
        "type": source_type,
        "base_url": feed_url,
        "priority": priority,
        "priority_tier": priority_tier,
        "enabled": False if unsupported else (True if enabled is None else enabled),
        "config": config,
    }


def _page(
    label: str,
    url: str,
    source_type: SourceType,
    *,
    vendor: str | None = None,
    article_selector: str = "article, main li, .card, .event-card",
    title_selector: str = "h1, h2, h3, a",
    link_selector: str = "a",
    note_selector: str | None = None,
    priority_tier: str = "D",
    cadence_minutes: int | None = None,
    priority: int = 1,
    query_terms: list[str] | None = None,
    note: str | None = None,
    unsupported: bool = False,
    unsupported_reason: str | None = None,
    enabled: bool | None = None,
) -> dict[str, Any]:
    interval = cadence_minutes if cadence_minutes is not None else _TIER_CADENCE_MINUTES[priority_tier]
    config: dict[str, Any] = {
        "url": url,
        "vendor": vendor,
        "article_selector": article_selector,
        "title_selector": title_selector,
        "link_selector": link_selector,
        "query_terms": query_terms or DEFAULT_QUERY_TERMS,
        "poll_interval_minutes": interval,
    }
    if note_selector:
        config["note_selector"] = note_selector
    if note:
        config["note"] = note
    if unsupported:
        config["unsupported"] = True
        config["unsupported_reason"] = unsupported_reason or "Blocked by site policy"
    return {
        "name": _source_name(source_type, label),
        "type": source_type,
        "base_url": url,
        "priority": priority,
        "priority_tier": priority_tier,
        "enabled": False if unsupported else (True if enabled is None else enabled),
        "config": config,
    }


SOURCE_DEFINITIONS: list[dict[str, Any]] = [
    # Official vendor RSS/blog feeds (Tier B).
    _feed(
        "AWS Training and Certification Blog",
        "https://aws.amazon.com/blogs/training-and-certification/feed/",
        SourceType.BLOG,
        vendor="AWS",
    ),
    _feed(
        "AWS Training Announcements",
        "https://aws.amazon.com/blogs/training-and-certification/category/post-types/announcements/feed/",
        SourceType.BLOG,
        vendor="AWS",
        priority=2,
    ),
    _feed(
        "AWS Builder",
        "https://builder.aws.com/rss.xml",
        SourceType.RSS,
        vendor="AWS",
        priority=2,
    ),
    _feed(
        "Microsoft Learn Blog",
        (
            "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/Community"
            "?interaction.style=blog&labels=Microsoft+Learn+Blog"
        ),
        SourceType.BLOG,
        vendor="Microsoft",
    ),
    _feed(
        "Google Cloud Blog",
        "https://cloudblog.withgoogle.com/rss/",
        SourceType.BLOG,
        vendor="Google Cloud",
    ),
    _feed(
        "Cisco Newsroom",
        "https://newsroom.cisco.com/c/services/i/servlets/newsroom/rssfeed.json",
        SourceType.BLOG,
        vendor="Cisco",
    ),
    _feed(
        "Red Hat Blog",
        "https://www.redhat.com/en/rss/blog",
        SourceType.BLOG,
        vendor="Red Hat",
    ),
    _feed(
        "Linux Foundation Blog",
        "https://www.linuxfoundation.org/blog/rss.xml",
        SourceType.BLOG,
        vendor="Linux Foundation",
    ),
    _feed(
        "Linux.com",
        "https://www.linux.com/feed/",
        SourceType.RSS,
        vendor="Linux Foundation",
    ),

    # Community/forum RSS feeds (Tier C).
    _feed(
        "Microsoft Learn Q&A Voucher Search",
        "https://learn.microsoft.com/api/search/rss?search=voucher+certification+exam&locale=en-us",
        SourceType.FORUM,
        vendor="Microsoft",
        priority_tier="C",
        priority=2,
    ),
    _feed(
        "Google Cloud Training Group",
        "https://discuss.google.dev/c/google-cloud/cloud-announcements/172.rss",
        SourceType.FORUM,
        vendor="Google Cloud",
        priority_tier="C",
        note=(
            "Migrated from Google Groups to discuss.google.dev. "
            "Category 172 = Cloud Announcements."
        ),
    ),
    _feed(
        "Microsoft Events",
        "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=azure-events",
        SourceType.BLOG,
        vendor="Microsoft",
        priority=2,
    ),

    # Aggregator blogs (Tier C).
    _feed(
        "Tutorials Dojo",
        "https://tutorialsdojo.com/feed/",
        SourceType.RSS,
        vendor="Tutorials Dojo",
        priority_tier="C",
    ),
    _feed(
        "Packet Pilot",
        "https://packetpilot.com/feed/",
        SourceType.RSS,
        vendor="Packet Pilot",
        priority_tier="C",
    ),
    {
        "name": "rss:cloud_academy_blog",
        "type": SourceType.WEBSITE,
        "base_url": "https://www.pluralsight.com/resources/blog",
        "priority": 1,
        "priority_tier": "C",
        "enabled": False,
        "config": {
            "collector": "website",
            "url": "https://www.pluralsight.com/resources/blog",
            "article_selector": "a[href*='/resources/blog/']",
            "title_selector": "p",
            "link_selector": "self",
            "vendor": "Pluralsight",
            "unsupported": True,
            "unsupported_reason": (
                "Pluralsight Enterprise ToS forbid robots/crawlers/data-mining tools "
                "not provided by Pluralsight. Prefer official feeds/APIs only."
            ),
            "query_terms": DEFAULT_QUERY_TERMS,
            "poll_interval_minutes": 240,
        },
    },
    _feed(
        "Microsoft Blog",
        "https://blogs.microsoft.com/feed",
        SourceType.RSS,
        vendor="Microsoft",
    ),
    _feed(
        "Cisco Newsroom",
        "https://newsroom.cisco.com/c/services/i/servlets/newsroom/rssfeed.json",
        SourceType.RSS,
        vendor="Cisco",
    ),
    _feed(
        "Cisco Newsroom Security",
        "https://newsroom.cisco.com/c/services/i/servlets/newsroom/rssfeed.json?feed=security",
        SourceType.RSS,
        vendor="Cisco",
    ),
    _feed(
        "Cisco Newsroom Press",
        "https://newsroom.cisco.com/c/services/i/servlets/newsroom/rssfeed.json?feed=press-releases",
        SourceType.RSS,
        vendor="Cisco",
    ),

    # Official vendor/event pages (Tier D).
    _page(
        "Microsoft Cloud Skills Challenge",
        "https://learn.microsoft.com/training/challenges",
        SourceType.EVENT,
        vendor="Microsoft",
        article_selector="article, .card, li, main section",
    ),
    _page(
        "AWS Events",
        "https://aws.amazon.com/events/",
        SourceType.EVENT,
        vendor="AWS",
        article_selector=".lb-content-item, article, .card",
        title_selector="h2, h3, a",
        unsupported=True,
        unsupported_reason=(
            "AWS robots.txt / Customer Agreement discourage automated access to "
            "event pages. Use AWS Training & Certification RSS feeds instead."
        ),
    ),
    _page(
        "AWS reInvent",
        "https://aws.amazon.com/events/reinvent/",
        SourceType.EVENT,
        vendor="AWS",
        article_selector="main section, main",
        title_selector="h2, h3",
        unsupported=True,
        unsupported_reason=(
            "AWS event HTML scraping is high-risk per site policy. Prefer official "
            "AWS blog/announcement RSS."
        ),
    ),
    _page(
        "Google Cloud Events",
        "https://cloud.google.com/events",
        SourceType.EVENT,
        vendor="Google Cloud",
        article_selector="article, .event-item, .card",
        note="Conditional HTML — robots-aware, slow poll. Prefer Google Cloud blog RSS.",
    ),
    _page(
        "Google Cloud Next",
        "https://cloud.withgoogle.com/next",
        SourceType.EVENT,
        vendor="Google Cloud",
        article_selector="article, .card, main section",
        note="Conditional HTML — robots-aware, slow poll.",
    ),
    _page(
        "Cisco Live",
        "https://www.ciscolive.com/global.html",
        SourceType.EVENT,
        vendor="Cisco",
        article_selector=".cmp-teaser, article, .card",
        title_selector="h2, h3, a",
        unsupported=True,
        unsupported_reason=(
            "Cisco Terms forbid crawling/bots/scripts. Use Cisco Newsroom RSS only."
        ),
    ),
    _page(
        "CompTIA Offers",
        "https://www.comptia.org/en-us/blog/",
        SourceType.WEBSITE,
        vendor="CompTIA",
        article_selector="main li",
        title_selector="a",
        link_selector="a",
        note="Conditional HTML — robots-aware, ≤0.5 req/s via global scrape policy.",
    ),
    _page(
        "ISC2 Blog",
        "https://www.isc2.org/Insights",
        SourceType.WEBSITE,
        vendor="ISC2",
        unsupported=True,
        unsupported_reason=(
            "ISC2 Site Use Policy forbids bots/scrapers without permission. "
            "Use official APIs/feeds only."
        ),
    ),
    _feed(
        "Oracle University Blog",
        "https://feeds.libsyn.com/459162/rss",
        SourceType.BLOG,
        vendor="Oracle",
        priority_tier="D",
        note=(
            "Podcast RSS - blog /rss is 403. Podcast actively covers Race to "
            "Certification and free exam promos."
        ),
    ),
    _page(
        "Red Hat Training Specials",
        "https://www.redhat.com/en/services/training/specials",
        SourceType.WEBSITE,
        vendor="Red Hat",
        article_selector="article, .card, main section, main li",
        title_selector="h2, h3, a",
        link_selector="a",
        unsupported=True,
        unsupported_reason=(
            "Red Hat site TOS forbid robot/spider retrieval apps; robots.txt "
            "sets Crawl-delay 10. Use Red Hat Blog RSS only."
        ),
    ),

    # Aggregators without reliable known feeds (Tier C).
    _page(
        "MSFTHub Vouchers",
        "https://msfthub.com/vouchers/",
        SourceType.WEBSITE,
        vendor="MSFTHub",
        article_selector="li",
        title_selector="span",
        link_selector="a",
        priority_tier="C",
        priority=2,
        note_selector="aside.starlight-aside--note .starlight-aside__content",
    ),
    _page(
        "VladTalksTech",
        "https://vladtalkstech.com/",
        SourceType.WEBSITE,
        vendor="VladTalksTech",
        priority_tier="C",
    ),
]


async def bootstrap_data() -> None:
    """Populate sources and keywords. Safe to re-run."""
    logger.info("Running database bootstrap")
    async with AsyncSessionLocal() as session:
        for kw in KEYWORDS:
            await session.execute(
                insert(Keyword)
                .values(keyword=kw["keyword"].lower(), score=kw["score"], enabled=True)
                .on_conflict_do_nothing(index_elements=["keyword"])
            )

        for sub in HIGH_SIGNAL_REDDIT_SUBREDDITS:
            tier = _reddit_tier(sub)
            cadence = _TIER_CADENCE_MINUTES[tier]
            await session.execute(
                insert(Source)
                .values(
                    name=f"reddit:{sub.lower()}",
                    type=SourceType.REDDIT,
                    base_url=f"https://www.reddit.com/r/{sub}",
                    enabled=True,
                    priority=1 if tier == "A" else 2,
                    priority_tier=tier,
                    config={
                        "subreddit": sub,
                        "query_terms": DEFAULT_QUERY_TERMS,
                        "poll_interval_minutes": cadence,
                        "auth_mode": "praw_or_rss",
                    },
                )
                .on_conflict_do_nothing(index_elements=["name"])
            )

        for source in SOURCE_DEFINITIONS:
            enabled = source.get("enabled", True)
            await session.execute(
                insert(Source)
                .values(
                    name=source["name"],
                    type=source["type"],
                    base_url=source["base_url"],
                    enabled=enabled,
                    priority=source.get("priority", 1),
                    priority_tier=source.get("priority_tier", "C"),
                    config=source["config"],
                )
                .on_conflict_do_update(
                    index_elements=["name"],
                    set_={
                        "type": source["type"],
                        "base_url": source["base_url"],
                        "enabled": enabled,
                        "priority": source.get("priority", 1),
                        "priority_tier": source.get("priority_tier", "C"),
                        "config": source["config"],
                    },
                )
            )

        for sub in DISABLED_REDDIT_SUBREDDITS:
            await session.execute(
                update(Source)
                .where(Source.name == f"reddit:{sub.lower()}")
                .values(enabled=False)
            )

        await session.commit()

    logger.info("Database bootstrap complete")
