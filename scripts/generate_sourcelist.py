"""Generate sourcelist.md from bootstrap source definitions."""
from __future__ import annotations

from pathlib import Path

from voucherbot.config.settings import settings
from voucherbot.database.bootstrap import (
    HIGH_SIGNAL_REDDIT_SUBREDDITS,
    SOURCE_DEFINITIONS,
    _TIER_CADENCE_MINUTES,
    _reddit_tier,
)
from voucherbot.models.source import SourceType


def fmt_interval(minutes: int) -> str:
    if minutes < 60:
        return f"every {minutes} min"
    if minutes < 1440:
        hours = minutes / 60
        return f"every {hours:g} h ({minutes} min)"
    days = minutes / 1440
    return f"every {days:g} d ({minutes} min)"


def fetches_per_day(minutes: int) -> float:
    return round(1440 / minutes, 1)


def fetch_limit(source_type: SourceType) -> int:
    return settings.reddit_fetch_limit if source_type == SourceType.REDDIT else 25


def main() -> None:
    rows: list[dict] = []

    for sub in HIGH_SIGNAL_REDDIT_SUBREDDITS:
        tier = _reddit_tier(sub)
        cadence = _TIER_CADENCE_MINUTES[tier]
        limit = fetch_limit(SourceType.REDDIT)
        rows.append(
            {
                "slug": f"reddit:{sub.lower()}",
                "type": "REDDIT",
                "tier": tier,
                "poll_min": cadence,
                "interval": fmt_interval(cadence),
                "fetch": limit,
                "max_per_day": int(fetches_per_day(cadence) * limit),
                "url": f"https://www.reddit.com/r/{sub}",
                "collector": "RedditCollector",
                "notes": "Keyword search (OR of query_terms) when PRAW configured; else RSS fallback",
            }
        )

    for source in SOURCE_DEFINITIONS:
        config = source["config"]
        source_type: SourceType = source["type"]
        tier = source.get("priority_tier", "C")
        poll = config.get("poll_interval_minutes", _TIER_CADENCE_MINUTES.get(tier, 240))
        if "feed_url" in config:
            collector = "RssCollector"
            url = config["feed_url"]
            notes = "Parses RSS/Atom/JSON feed; returns up to fetch limit newest items"
        else:
            collector = "WebsiteCollector"
            url = config.get("url", source.get("base_url", ""))
            notes = "Scrapes HTML page via CSS selectors; returns up to fetch limit matches"
        limit = fetch_limit(source_type)
        rows.append(
            {
                "slug": source["name"],
                "type": source_type.value,
                "tier": tier,
                "poll_min": poll,
                "interval": fmt_interval(poll),
                "fetch": limit,
                "max_per_day": int(fetches_per_day(poll) * limit),
                "url": url,
                "collector": collector,
                "notes": config.get("note", notes),
            }
        )

    rows.sort(key=lambda row: (row["tier"], row["type"], row["slug"]))

    lines = [
        "# VoucherBot Source List",
        "",
        "Auto-generated from `voucherbot/database/bootstrap.py` and runtime settings.",
        "",
        "## How fetching works",
        "",
        "- **Scheduler:** one DB-driven tick every **2 minutes**; each tick processes **exactly one source** (whichever is most overdue).",
        "- **Fetch limit:** max items requested from the collector **per poll** (before keyword filtering, dedup, and AI).",
        f"- **Reddit fetch limit:** `settings.reddit_fetch_limit` = **{settings.reddit_fetch_limit}** posts/search",
        "- **All other sources:** default fetch limit = **25** items per poll",
        "- **Keyword filter:** posts scoring below threshold are dropped after fetch (not stored).",
        "- **Tier cadence defaults:** A=15 min, B=60 min, C=240 min (4 h), D=720 min (12 h)",
        "",
        "## Tier summary",
        "",
        "| Tier | Poll interval | Queue priority | Sources | ~Max items/day (tier total) |",
        "|------|---------------|----------------|---------|------------------------------|",
    ]

    for tier in ("A", "B", "C", "D"):
        tier_rows = [row for row in rows if row["tier"] == tier]
        if not tier_rows:
            continue
        cadence = _TIER_CADENCE_MINUTES[tier]
        max_day = sum(row["max_per_day"] for row in tier_rows)
        lines.append(
            f"| {tier} | {fmt_interval(cadence)} | Highest first | {len(tier_rows)} | ~{max_day:,} |"
        )

    lines.extend(
        [
            "",
            f"**Total configured sources: {len(rows)}**",
            "",
            "> **Live DB note:** Bootstrap seeds these sources with `on_conflict_do_nothing`. "
            "Older rows in Postgres may differ (extra Reddit subs, legacy names). "
            "This file reflects the **current code configuration** only.",
            "",
            "## All sources",
            "",
            "| Source | Type | Tier | Poll interval | Items/poll | ~Max items/day | Collector | URL |",
            "|--------|------|------|---------------|------------|----------------|-----------|-----|",
        ]
    )

    for row in rows:
        display_url = row["url"]
        if len(display_url) > 70:
            display_url = display_url[:67] + "..."
        lines.append(
            f"| {row['slug']} | {row['type']} | {row['tier']} | {row['interval']} "
            f"| {row['fetch']} | {row['max_per_day']} | {row['collector']} | {display_url} |"
        )

    lines.extend(["", "## Notes", ""])
    for row in rows:
        if row["type"] == "REDDIT" or row["notes"] not in (
            "Parses RSS/Atom/JSON feed; returns up to fetch limit newest items",
            "Scrapes HTML page via CSS selectors; returns up to fetch limit matches",
        ):
            lines.append(f"- **{row['slug']}:** {row['notes']}")

    output = Path(__file__).resolve().parents[1] / "sourcelist.md"
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {output} ({len(rows)} sources)")


if __name__ == "__main__":
    main()
