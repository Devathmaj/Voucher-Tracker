"""Verify all bootstrap sources return data or are explicitly marked unsupported."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from voucherbot.database.bootstrap import SOURCE_DEFINITIONS
from voucherbot.models.source import SourceType
from voucherbot.providers.rss.collector import RssCollector
from voucherbot.providers.website.collector import WebsiteCollector

COLLECTORS = {
    SourceType.RSS: RssCollector(),
    SourceType.BLOG: RssCollector(),
    SourceType.FORUM: RssCollector(),
    SourceType.WEBSITE: WebsiteCollector(),
    SourceType.EVENT: WebsiteCollector(),
}


async def verify_source(source: dict) -> dict:
    name = source["name"]
    config = source["config"]

    if config.get("unsupported"):
        return {
            "name": name,
            "status": "unsupported",
            "reason": config.get("unsupported_reason"),
        }

    stype = source["type"]
    collector = COLLECTORS.get(stype)
    if collector is None:
        return {"name": name, "status": "skip", "reason": f"no collector for {stype}"}

    try:
        posts = await collector.collect(config, limit=3)
        if posts:
            return {
                "name": name,
                "status": "ok",
                "count": len(posts),
                "sample": posts[0].title[:80],
            }
        return {"name": name, "status": "empty", "url": source["base_url"]}
    except Exception as exc:
        return {"name": name, "status": "error", "error": str(exc), "url": source["base_url"]}


async def main() -> int:
    results = await asyncio.gather(*(verify_source(source) for source in SOURCE_DEFINITIONS))
    ok = [result for result in results if result["status"] == "ok"]
    unsupported = [result for result in results if result["status"] == "unsupported"]
    bad = [result for result in results if result["status"] not in {"ok", "unsupported"}]

    print(f"OK: {len(ok)} / {len(results)}")
    print(f"Unsupported: {len(unsupported)}")
    for result in unsupported:
        print(f"  [unsupported] {result['name']}: {result.get('reason')}")

    if bad:
        print(f"FAILURES: {len(bad)}")
        for result in bad:
            detail = result.get("url") or result.get("reason") or result.get("error")
            print(f"  [{result['status']}] {result['name']}: {detail}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
