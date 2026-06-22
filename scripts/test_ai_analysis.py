"""
Manual smoke-test: fetch 3-5 posts from real RSS deal feeds and run them
through the Gemini AI analyzer. No database, no APScheduler -- just a direct
end-to-end check that the analyzer is wired and responding correctly.

Run from the project root:
    python scripts/test_ai_analysis.py
"""
import asyncio
import json
import sys
import textwrap

# Force UTF-8 on Windows consoles that default to cp1252
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from voucherbot.providers.rss.collector import RssCollector
from voucherbot.services.ai.analyzer import analyze_post, _initialized

# Well-known public deal/voucher RSS feeds
RSS_FEEDS = [
    "https://www.hotukdeals.com/rss/deals",
    "https://www.dealnews.com/rss/",
]

FETCH_LIMIT = 3   # posts per feed (we want 3-5 total)

DIV_THICK  = "=" * 72
DIV_THIN   = "-" * 72
DIV_DOT    = "." * 72


async def main() -> None:
    print(DIV_THICK)
    print("  VoucherBot - AI Analyzer Smoke-Test")
    print(DIV_THICK)

    if not _initialized:
        print("\n[WARN] GEMINI_API_KEY is not set -- analyzer cannot run. Aborting.")
        return

    collector = RssCollector()
    all_posts = []

    for feed_url in RSS_FEEDS:
        print(f"\n[RSS] Fetching from: {feed_url}")
        posts = await collector.collect({"feed_url": feed_url}, limit=FETCH_LIMIT)
        print(f"      -> {len(posts)} post(s) returned")
        all_posts.extend(posts)
        if len(all_posts) >= 5:
            break

    # Trim to at most 5 posts
    all_posts = all_posts[:5]

    if not all_posts:
        print("\n[ERROR] No posts fetched. Check network / feed URLs.")
        return

    print(f"\n{DIV_THIN}")
    print(f"  Analysing {len(all_posts)} post(s) via Gemini...")
    print(DIV_THIN)

    for idx, post in enumerate(all_posts, start=1):
        print(f"\n[{idx}/{len(all_posts)}] {post.title[:80]}")
        print(f"  URL     : {post.url}")
        preview = (post.content or "(no content)")[:200].replace("\n", " ")
        print(f"  Content : {preview}...")

        result = await analyze_post(title=post.title, content=post.content)

        if idx < len(all_posts):
            await asyncio.sleep(3)   # stay under free-tier RPM limit

        if result is None:
            print("  AI      : [WARN] No response (API error or key missing)")
        else:
            is_v       = result.get("is_voucher")
            confidence = result.get("confidence", 0.0)
            reason     = result.get("reason", "")
            code       = result.get("voucher_code") or "none"
            tag        = "[VOUCHER]" if is_v else "[NOT VOUCHER]"

            print(f"  AI      : {tag}  is_voucher={is_v}  confidence={confidence:.2f}")
            wrapped = textwrap.fill(reason, width=66, subsequent_indent=" " * 14)
            print(f"  Reason  : {wrapped}")
            print(f"  Code    : {code}")

        print(DIV_DOT)

    print(f"\n{DIV_THICK}")
    print("  Done.")
    print(DIV_THICK)


if __name__ == "__main__":
    asyncio.run(main())
