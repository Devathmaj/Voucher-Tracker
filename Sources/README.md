# Source Catalog

Human-readable reference for all official ingestion sources. The **authoritative runtime catalog** is [`voucherbot/database/bootstrap.py`](../voucherbot/database/bootstrap.py), which seeds the database on app startup.

## Files

| File | Contents |
|------|----------|
| [`Subreddit.txt`](Subreddit.txt) | Reddit subreddits (Tier A/B), plus disabled subs |
| [`RSS_List.txt`](RSS_List.txt) | RSS, blog, and forum feeds |
| [`Website_List.txt`](Website_List.txt) | HTML scrapers (vendor pages, aggregators) |
| [`Event_List.txt`](Event_List.txt) | Vendor event listing pages |

## Scheduling defaults

| Tier | Poll interval | Queue priority |
|------|---------------|----------------|
| A | 15 min | Highest |
| B | 60 min | High |
| C | 4 h | Medium |
| D | 12 h | Low |

## Fetch limits (per poll)

| Collector | Items requested |
|-----------|-----------------|
| Reddit | 25 (`REDDIT_FETCH_LIMIT`) |
| RSS / Website | 25 |

Reddit ingestion is gated by `REDDIT_INGESTION_ENABLED` in `.env` (default `false`).

## Verify sources

```bash
python scripts/verify_sources.py
```
