import requests
from bs4 import BeautifulSoup
import hashlib
import json
import time
from datetime import datetime, timezone

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

# ─────────────────────────────────────────────────────────────────────────────
# SOURCE CATALOG
# ─────────────────────────────────────────────────────────────────────────────
#
# KEY FINDINGS from live fetches:
#
# VENDOR ACADEMIES:
#   aws.amazon.com/training    → Static hub page. Promos appear as card tiles
#                                with <a> + heading + description. No dedicated
#                                promo page — the T&C blog RSS (already in your
#                                catalog) is the better promo signal. Scrape
#                                /training/events/ for free event vouchers.
#
#   redhat.com/specials        → Drupal static page. Well-structured: h3 heading
#                                + p description per promo block. LIVE NOW:
#                                15% referral discount code. Clean to scrape.
#
#   ibm.com/training           → JS-heavy SPA. Nothing useful renders without
#                                JS execution. SKIP — no static promo surface.
#
#   snowflake.com/certifications → Marketing page, no promo content.
#                                Real promos live on learn.snowflake.com as
#                                event/webinar pages that include free vouchers.
#                                Scrape: learn.snowflake.com + snowflake.com/blog
#
#   databricks.com/certification → Static info pages per cert. Free accreditation
#                                exams (for customers/partners) mentioned inline.
#                                Scrape: databricks.com/learn/certification
#                                (index page) for any "free" mentions.
#
#   broadcom.com/support/education → Broadcom/VMware — JS-rendered, no useful
#                                static content. SKIP.
#
# EVENT PLATFORMS:
#   sessionize.com/cfp         → Public listing of open CFPs. Static HTML grid
#                                of event cards. Promos/vouchers sometimes listed
#                                in event descriptions. Valid to scrape.
#
# ─────────────────────────────────────────────────────────────────────────────

SOURCES = {
    # ── VENDOR ACADEMIES ─────────────────────────────────────────────────────
    "AWS Training Events": {
        # Free training events often include exam vouchers for attendees
        # This is the dedicated events page, distinct from the main /training/ hub
        "url": "https://aws.amazon.com/training/events/",
        "extractor": "aws_events",
        "tier": "C",
        "poll_min": 240,
    },
    "Red Hat Training Specials": {
        # Drupal static page — h3 + p blocks per promo. Currently shows
        # 15% referral discount. Clean scrape, no JS needed.
        "url": "https://www.redhat.com/en/services/training/specials",
        "extractor": "redhat_specials",
        "tier": "C",
        "poll_min": 240,
    },
    "Databricks Certification": {
        # Static index page. Free accreditation exams for customers/partners
        # mentioned inline. Worth scanning for "free" keyword hits.
        "url": "https://www.databricks.com/learn/certification",
        "extractor": "generic_cards",
        "tier": "D",
        "poll_min": 720,
    },
    # ── SKIPPED (confirmed JS-only or no static promo surface) ───────────────
    # IBM Training      → Full SPA, nothing renders without JS
    # Broadcom/VMware   → JS-rendered, no static promo content
    # Google Cloud Skills Boost → login-gated
    # Cisco U           → login-gated
    # Oracle University → homepage banner only, low signal
    # ── EVENT PLATFORMS ──────────────────────────────────────────────────────
    # In SOURCES dict:
    "Snowflake SnowPro Blog": {
        "url": "https://www.snowflake.com/en/blog/authors/snowpro-certification-team/",
        "extractor": "snowflake_blog",  # ← was "generic_cards"
        "tier": "D",
        "poll_min": 720,
    },
    "Sessionize User Groups": {
        "url": "https://sessionize.com/user-groups/",
        "extractor": "sessionize_usergroups",  # ← was "sessionize_cfp"
        "tier": "D",
        "poll_min": 720,
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# KEYWORD FILTER
# ─────────────────────────────────────────────────────────────────────────────

VOUCHER_KEYWORDS = [
    "voucher",
    "free exam",
    "free certification",
    "beta exam",
    "discount",
    "promo",
    "promotion",
    "retake",
    "% off",
    "no cost",
    "complimentary",
    "exam credit",
    "free trial",
    "sponsored",
    "free access",
    "free badge",
    "waived",
    "free training",
    "free course",
    "free voucher",
]


# ─────────────────────────────────────────────────────────────────────────────
# HTTP
# ─────────────────────────────────────────────────────────────────────────────


def fetch(url: str) -> requests.Response | None:
    try:
        r = requests.get(
            url,
            headers={"User-Agent": BROWSER_UA},
            timeout=15,
            allow_redirects=True,
        )
        r.raise_for_status()
        return r
    except requests.RequestException as e:
        print(f"    ⚠️  {e}")
        return None


def strip_boilerplate(soup: BeautifulSoup) -> BeautifulSoup:
    for tag in soup.select("nav, footer, header, script, style, [aria-hidden='true']"):
        tag.decompose()
    return soup


# ─────────────────────────────────────────────────────────────────────────────
# EXTRACTORS
# ─────────────────────────────────────────────────────────────────────────────


def extract_aws_events(soup: BeautifulSoup) -> list[dict]:
    """
    aws.amazon.com/training/events/
    Cards: <div> or <li> containing <a href> + heading + description.
    Also catches any inline "free" / "voucher" promo banners.
    """
    items = []
    strip_boilerplate(soup)

    # Each event card has a heading + optional description + link
    for heading in soup.find_all(["h2", "h3", "h4"]):
        title = heading.get_text(strip=True)
        if not title or len(title) < 5:
            continue
        # Nearest anchor (could be parent or next sibling)
        a = heading.find("a") or heading.find_parent("a") or heading.find_next("a")
        url = a["href"] if a and a.get("href") else ""
        # Make relative URLs absolute
        if url.startswith("/"):
            url = "https://aws.amazon.com" + url

        desc_el = heading.find_next_sibling("p")
        desc = desc_el.get_text(strip=True) if desc_el else ""

        items.append({"title": title, "description": desc, "url": url})

    return items


def extract_redhat_specials(soup: BeautifulSoup) -> list[dict]:
    """
    redhat.com/en/services/training/specials
    Drupal page: h2/h3 headings introduce each promo block,
    followed by one or more <p> tags with description.
    Confirmed live content: "Red Hat Training Referral Program" — 15% discount.
    """
    items = []
    strip_boilerplate(soup)
    main = soup.find("main") or soup.body

    for h in main.find_all(["h2", "h3"]):
        title = h.get_text(strip=True)
        if not title or len(title) < 5:
            continue
        # Skip section titles that are nav/structural
        if any(
            skip in title.lower()
            for skip in ["skip to", "menu", "search", "navigation"]
        ):
            continue

        # Collect paragraph siblings until next heading
        desc_parts = []
        for sib in h.find_next_siblings():
            if sib.name in ("h2", "h3", "h4"):
                break
            if sib.name == "p":
                text = sib.get_text(strip=True)
                if text:
                    desc_parts.append(text)

        # Find any link in the block
        block_a = h.find_next("a", href=True)
        url = block_a["href"] if block_a else ""
        if url.startswith("/"):
            url = "https://www.redhat.com" + url

        items.append(
            {
                "title": title,
                "description": " ".join(desc_parts[:3]),  # first 3 paras
                "url": url,
            }
        )

    return items


def extract_sessionize_cfp(soup: BeautifulSoup) -> list[dict]:
    """
    sessionize.com/cfp
    Public CFP listing: each event is a card with event name, date range,
    and a short description. We capture everything and rely on keyword
    filtering to surface events that offer vouchers/sponsored attendance.
    """
    items = []
    strip_boilerplate(soup)

    # Sessionize CFP cards use article elements or divs with class patterns
    # Try article first, then fall back to heading-based scan
    cards = (
        soup.select("article")
        or soup.select("[class*='event']")
        or soup.select("[class*='card']")
    )

    if cards:
        for card in cards:
            h = card.find(["h2", "h3", "h4", "h5"])
            p = card.find("p")
            a = card.find("a", href=True)
            title = h.get_text(strip=True) if h else ""
            desc = p.get_text(strip=True) if p else ""
            url = a["href"] if a else ""
            if url.startswith("/"):
                url = "https://sessionize.com" + url
            if title:
                items.append({"title": title, "description": desc, "url": url})
    else:
        # Fallback: heading scan
        for h in soup.find_all(["h2", "h3", "h4"]):
            title = h.get_text(strip=True)
            if not title or len(title) < 5:
                continue
            a = h.find("a") or h.find_parent("a") or h.find_next("a")
            url = a["href"] if a and a.get("href") else ""
            desc_el = h.find_next_sibling("p")
            desc = desc_el.get_text(strip=True) if desc_el else ""
            items.append({"title": title, "description": desc, "url": url})

    return items


def extract_generic_cards(soup: BeautifulSoup) -> list[dict]:
    """
    Generic fallback: heading + next-sibling paragraph.
    Used for: Snowflake blog, Databricks certification index.
    """
    items = []
    strip_boilerplate(soup)
    main = soup.find("main") or soup.body

    for h in main.find_all(["h2", "h3", "h4"]):
        title = h.get_text(strip=True)
        if not title or len(title) < 5:
            continue
        desc_el = h.find_next_sibling("p")
        desc = desc_el.get_text(strip=True) if desc_el else ""
        a = h.find("a") or h.find_parent("a") or h.find_next("a")
        url = a["href"] if a and a.get("href") else ""
        items.append({"title": title, "description": desc, "url": url})

    return items


def extract_snowflake_blog(soup: BeautifulSoup) -> list[dict]:
    """
    snowflake.com author/category pages.
    Posts render as a flat <a href="..."> per article containing:
      date text + category text + title text — all inline, no heading wrapper.
    We grab every <a> that links to /en/blog/ and use its full text as title.
    """
    items = []
    strip_boilerplate(soup)

    for a in soup.find_all("a", href=True):
        href = a["href"]
        # Only blog post links
        if "/en/blog/" not in href:
            continue
        # Skip nav/footer links (very short text)
        text = a.get_text(separator=" ", strip=True)
        if len(text) < 15:
            continue
        # Make absolute
        if href.startswith("/"):
            href = "https://www.snowflake.com" + href

        items.append({"title": text, "description": "", "url": href})

    # Deduplicate by URL
    seen = set()
    unique = []
    for item in items:
        if item["url"] not in seen:
            seen.add(item["url"])
            unique.append(item)
    return unique


def extract_sessionize_usergroups(soup: BeautifulSoup) -> list[dict]:
    """
    sessionize.com/user-groups/
    Each event is a <section> containing:
      <h3><a href="/slug">Event Name</a></h3>
      <ul> with location / date / type / CFP status items
      <p> description text
    """
    items = []
    strip_boilerplate(soup)

    for section in soup.find_all("section"):
        h = section.find(["h2", "h3", "h4"])
        if not h:
            continue
        title = h.get_text(strip=True)
        if not title or len(title) < 3:
            continue

        a = h.find("a", href=True)
        url = a["href"] if a else ""
        if url.startswith("/"):
            url = "https://sessionize.com" + url

        # Grab description — first <p> that isn't just a truncation notice
        desc = ""
        for p in section.find_all("p"):
            t = p.get_text(strip=True)
            if t and len(t) > 20 and "Show more" not in t:
                desc = t
                break

        # Also grab CFP status from <ul> items for keyword matching
        meta = " ".join(li.get_text(strip=True) for li in section.find_all("li"))

        items.append(
            {
                "title": title,
                "description": desc,
                "meta": meta,
                "url": url,
            }
        )

    return items


EXTRACTORS = {
    "aws_events": extract_aws_events,
    "redhat_specials": extract_redhat_specials,
    "snowflake_blog": extract_snowflake_blog,  # ← new
    "sessionize_usergroups": extract_sessionize_usergroups,  # ← new
    "generic_cards": extract_generic_cards,
}

# ─────────────────────────────────────────────────────────────────────────────
# RELEVANCE
# ─────────────────────────────────────────────────────────────────────────────


def is_relevant(item: dict) -> bool:
    text = " ".join(
        [
            item.get("title", ""),
            item.get("description", ""),
            item.get("meta", ""),  # ← add this
        ]
    ).lower()
    return any(kw in text for kw in VOUCHER_KEYWORDS)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN SCRAPER
# ─────────────────────────────────────────────────────────────────────────────


def scrape_source(name: str, config: dict) -> dict:
    url = config["url"]
    extractor_fn = EXTRACTORS[config["extractor"]]

    resp = fetch(url)
    if not resp:
        return {
            "source": name,
            "url": url,
            "error": True,
            "items": [],
            "relevant": [],
        }

    if resp.url != url:
        print(f"    ↳ Redirected → {resp.url}")

    soup = BeautifulSoup(resp.text, "html.parser")
    content_hash = hashlib.md5(resp.text.encode()).hexdigest()
    items = extractor_fn(soup)
    relevant = [i for i in items if is_relevant(i)]

    return {
        "source": name,
        "url": url,
        "final_url": resp.url,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "tier": config.get("tier", "D"),
        "poll_min": config.get("poll_min", 720),
        "hash": content_hash,
        "total_items": len(items),
        "items": items,
        "relevant": relevant,
    }


def main():
    results = []

    for name, config in SOURCES.items():
        print(f"\n🔍 {name}")
        print(f"   {config['url']}")

        result = scrape_source(name, config)

        if result.get("error"):
            print(f"   ❌ Failed to fetch")
        else:
            count = result["total_items"]
            hits = len(result["relevant"])
            flag = "🎯" if hits else "  "
            print(f"   {flag} {count} items, {hits} relevant")
            for item in result["relevant"]:
                print(f"      → {item['title'][:80]}")
                if item.get("url"):
                    print(f"        {item['url'][:80]}")

        results.append(result)
        time.sleep(2)

    with open("vendor_academies.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    total = sum(len(r["relevant"]) for r in results)
    print(f"\n{'─' * 60}")
    print(f"💾 Saved vendor_academies.json")
    print(f"🎯 {total} total relevant items across all sources")

    # Print Website_List.txt entries to add
    print(f"\n{'─' * 60}")
    print("📋 Entries to add to Website_List.txt:\n")
    for name, cfg in SOURCES.items():
        db_name = "website:" + name.lower().replace(" ", "_")
        print(
            f"[{cfg['tier']}] WEBSITE | {db_name} | {cfg['poll_min']} min | {cfg['url']}"
        )


if __name__ == "__main__":
    main()
