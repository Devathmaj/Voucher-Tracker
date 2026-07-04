# VoucherBot — Architecture

## Overview

VoucherBot is an async Python service that continuously monitors RSS feeds, vendor blogs, event pages, and Reddit subreddits for IT/cloud certification vouchers and promotions. When a voucher is detected, it sends an email alert via Resend.

The system runs as a single-process FastAPI application backed by a PostgreSQL database. A background scheduler loop drives all data collection — there are no external job queues or worker processes.

---

## High-Level Data Flow

```
Sources (RSS / Web / Reddit)
        │
        ▼
  Collector (provider-specific)
        │  list[NormalizedPost]
        ▼
  Keyword Filter
        │  scored posts only
        ▼
  Deduplication (identity_hash / content_hash)
        │  new or changed posts only
        ▼
  AI Extraction (Groq → Gemini fallback)
        │  ExtractedEvent
        ▼
  Event Matcher (score-based dedup of promotions)
        │  canonical Event
        ▼
  Email Notification (Resend)
```

---

## Runtime Architecture

```
┌─────────────────────────────────────────────────────┐
│  FastAPI process (uvicorn)                          │
│                                                     │
│  ┌──────────────┐   ┌──────────────────────────┐   │
│  │  REST API    │   │  Background Scheduler     │   │
│  │  /health     │   │  asyncio Task (_run_loop) │   │
│  │  /ready      │   │                          │   │
│  │  /sources    │   │  sweep → dispatch_tick   │   │
│  │  /posts      │   │  → pipeline → sleep      │   │
│  │  /alerts     │   └──────────────────────────┘   │
│  └──────────────┘                                   │
└─────────────────────────────────────────────────────┘
              │
              ▼
     PostgreSQL (asyncpg / SQLAlchemy async)
```

The API and the scheduler share the same process and the same SQLAlchemy async engine. The scheduler runs as a single `asyncio.Task` started in the FastAPI `lifespan` context.

---

## Module Map

```
voucherbot/
├── main.py                  FastAPI app + lifespan (startup/shutdown)
├── config/settings.py       Pydantic Settings — all env vars + EventMatcherConfig
├── core/
│   ├── exceptions.py        Custom exception types
│   └── logging.py           structlog setup
├── database/
│   ├── connection.py        SQLAlchemy async engine + session factory
│   ├── init_db.py           create_all for non-prod
│   └── bootstrap.py        Seed sources + keywords on first run
├── models/
│   ├── source.py            Source, SourceType enum
│   ├── post.py              Post, PostStatus enum, VoucherPost view
│   ├── event.py             Event, EventStatus, MatchConfidence
│   ├── keyword.py           Keyword (scoring catalog)
│   └── pipeline_lock.py     Distributed lease row
├── providers/
│   ├── base.py              NormalizedPost dataclass + BaseCollector ABC
│   ├── http_policy.py       robots.txt, crawl-delay, polite_get
│   ├── rss/collector.py     RSS + Atom + JSON Feed parser
│   ├── reddit/
│   │   ├── client.py        asyncpraw wrapper
│   │   └── collector.py     PRAW search + RSS fallback
│   └── website/collector.py BeautifulSoup CSS-selector scraper
├── services/
│   ├── scheduler.py         _run_loop, _run_sweep, sleep-until-next-due
│   ├── dispatcher.py        Lease acquire/release, pick source, mark success/failure
│   ├── ingestion/
│   │   ├── pipeline.py      Orchestrates all 4 stages per source
│   │   ├── dedup.py         normalise_url, identity_hash, content_hash
│   │   └── event_matcher.py Score candidates, merge fields, create Event
│   ├── ai/
│   │   ├── analyzer.py      Groq + Gemini adapters, rate limiting, batch dispatch
│   │   └── schema.py        ExtractedEvent Pydantic model
│   └── email/
│       ├── sender.py        Resend API wrapper with throttle lock
│       └── notifications.py Build + send voucher alert email
└── api/routers/
    ├── health.py            GET /health, GET /ready
    ├── sources.py           GET /sources
    ├── posts.py             GET /posts
    └── alerts.py            GET /alerts (voucher_posts view)
```

---

## Scheduler

**File:** `voucherbot/services/scheduler.py`

The scheduler is a single `asyncio.Task` running `_run_loop`. It never uses APScheduler or Celery — scheduling state lives entirely in the `sources` table.

### Loop logic

```
while True:
    ran = await _run_sweep()       # process every due source sequentially
    sleep = await _seconds_until_next_due()
    await asyncio.sleep(sleep)     # capped at MAX_SLEEP_SECONDS (6 h)
```

### Sweep logic

Each sweep calls `dispatch_tick` in a loop until it returns `"idle"` (no more due sources). Sources are processed one at a time — sequential, not concurrent — to keep CPU flat.

### Due-source selection

A source is eligible when:
- `enabled = true`
- `next_due_at IS NULL OR next_due_at <= now()`
- `backoff_until IS NULL OR backoff_until <= now()`
- Reddit sources are excluded when `reddit_ingestion_enabled = false`

Sources are ordered by `next_due_at ASC NULLS FIRST, priority_tier ASC` with `SELECT ... FOR UPDATE SKIP LOCKED` to be safe for future multi-instance deployments.

### Priority tiers and poll intervals

| Tier | Default interval | Typical sources |
|------|-----------------|-----------------|
| A | 15 min | High-signal Reddit subs, key announcements |
| B | 60 min | Official vendor blogs |
| C | 240 min | Community forums, aggregators |
| D | 720 min | Event pages, podcast feeds |

Each source can override the interval via `config.poll_interval_minutes`.

---

## Dispatcher

**File:** `voucherbot/services/dispatcher.py`

The dispatcher owns the distributed lease and source lifecycle.

### Lease mechanism

A single row in `pipeline_lock` (name = `"pipeline"`) acts as a distributed mutex. Acquisition is an atomic `UPDATE ... WHERE holder IS NULL OR expires_at < now() RETURNING name`. The TTL is `tick_lease_ttl_seconds` (default 6 h). The lease is always released in a `finally` block.

This prevents two scheduler instances from processing the same source simultaneously if the service is ever scaled horizontally.

### Source lifecycle after a tick

**Success:**
- `consecutive_failures = 0`, `backoff_until = NULL`
- `next_due_at = now() + poll_interval_minutes`
- `avg_runtime_ms` updated with rolling average

**Failure (recoverable):**
- `consecutive_failures += 1`
- Exponential backoff: `base_minutes × 2^(failures-1)`, capped at `source_backoff_max_minutes` (default 360 min)
- `next_due_at = backoff_until`

**Failure (unrecoverable — 404, 403, 401, 410, etc.):**
- `enabled = false` immediately — source is permanently disabled, no backoff

---

## Ingestion Pipeline

**File:** `voucherbot/services/ingestion/pipeline.py`

`run_pipeline_for_source` runs four sequential stages for a single source per tick.

### Stage 0 — Collect

Resolves the correct collector from the source config:
- `SourceType.REDDIT` → `RedditCollector`
- config has `feed_url` → `RssCollector`
- config has `article_selector` → `WebsiteCollector`

Returns `list[NormalizedPost]`.

### Stage 1 — Keyword Filter

Each post's `title + content` is scored against the `keywords` table. Posts scoring below `SCORE_THRESHOLD = 1` are dropped. Sources with `note_selector` in their config (curated voucher pages like MSFTHub) bypass the filter entirely.

Sample keyword scores:

| Keyword | Score |
|---------|-------|
| voucher, coupon, promo code, free exam | 5 |
| free certification, discount, redeem | 4 |
| retake, limited time, beta access | 3 |
| certification, exam, webinar | 1 |

### Stage 2 — Deduplication

Two SHA-256 hashes per post:

- `identity_hash = SHA-256(normalise_url(url))` — stable page identity; never changes for the same page
- `content_hash = SHA-256(title|content|date)` — changes when the page is updated

Upsert logic (`INSERT ... ON CONFLICT DO UPDATE WHERE content_hash != new_hash`):
- New URL → INSERT, `status = QUEUED`
- Same URL, content changed → UPDATE title/content/content_hash, reset `status = QUEUED`
- Same URL, content unchanged → skip (rowcount = 0)

`normalise_url` strips tracking params (UTM, fbclid, gclid, etc.), forces `https`, lowercases the host, removes trailing slashes and fragments.

### Stage 3 — AI Extraction

Only new or updated posts reach the AI. Each post is sent to `analyze_post_batch` which distributes posts round-robin across available Groq models with a global concurrency semaphore of 4.

The AI returns an `ExtractedEvent` with:
- `is_voucher: bool` — whether the post has promotional intent
- `confidence: float` — 0.0–1.0
- Structured fields: `vendor`, `promotion_name`, `promotion_type`, `certifications`, `voucher_code`, `discount`, `registration_url`, `start_date`, `end_date`, `regions`

Posts where `is_voucher = false` are marked `FILTERED` and skipped.

### Stage 4 — Event Matching

For each AI-confirmed voucher, `EventMatcher.match_or_create` finds or creates a canonical `Event`.

**Candidate retrieval:** indexed lookup on `registration_url`, `voucher_code`, or `vendor` against `ACTIVE` events (max 20 candidates).

**Scoring:**

| Field | Weight | Match condition |
|-------|--------|-----------------|
| registration_url | 50 | exact normalised URL |
| voucher_code | 40 | exact, case-normalised |
| promotion_name | 20 | token-overlap similarity ≥ 0.60 |
| vendor | 15 | exact, lower-cased |
| certifications | 15 | at least one cert in common |
| date_overlap | 10 | date ranges overlap or both absent |

**Score bands (configurable):**

| Score | Outcome |
|-------|---------|
| ≥ 75 (`auto_merge_threshold`) | `AUTO_MERGED` — attach to existing Event |
| 60–74 (`possible_match_threshold`) | `POSSIBLE_MATCH` — attach but flag for review |
| < 60 | `NEW` — create a new Event |

**Field merging:** When attaching to an existing Event, fields are merged using `SOURCE_PRIORITY` (WEBSITE > EVENT > BLOG > RSS > FORUM > REDDIT > API). A higher-priority source's non-null value overwrites a lower-priority source's value. Every merge appends an audit entry to `event.merge_log` (JSONB array).

### Stage 5 — Email Notification

After the DB commit, `notify_voucher_found` sends an HTML + plain-text email via Resend for every `NEW` or `POSSIBLE_MATCH` post. `AUTO_MERGED` posts (same promotion seen again) do not trigger a new email. On successful send, `post.is_notified = true`.

---

## Providers

### BaseCollector

All collectors implement:
```python
async def collect(source_config: dict, limit: int) -> list[NormalizedPost]
```

`NormalizedPost` is a provider-agnostic dataclass with: `external_id`, `url`, `title`, `content`, `summary`, `author`, `published_at`, `raw_data`.

### RssCollector

- Fetches via `polite_get` (robots-aware)
- Falls back to `urllib` if `httpx` is blocked
- Detects JSON Feed format (`items` / `articles` / `data` keys) before attempting feedparser
- Uses `lxml` XML recovery for malformed feeds
- Rewrites known-broken Microsoft TechCommunity and Google Cloud Blog URLs
- If a feed entry has no summary, fetches the article page and extracts up to 2000 chars

### RedditCollector

- Primary: `asyncpraw` search with `query_terms` joined as `OR` expressions
- Fallback (no API credentials): Reddit's public `.rss` search endpoint via `polite_get`
- Controlled by `reddit_ingestion_enabled` setting (default `false`)

### WebsiteCollector

- CSS-selector driven: `article_selector`, `title_selector`, `link_selector` from source config
- `note_selector` extracts a structured note line (e.g. badge text on MSFTHub) prepended as `Note: <text>` to content — this bypasses keyword filtering downstream
- Skips sources with `unsupported: true` in config (ToS/policy blocks)

### HTTP Policy

**File:** `voucherbot/providers/http_policy.py`

All HTTP requests go through `polite_get` which:
1. Checks `robots.txt` (`is_allowed`) — raises `RobotsDisallowedError` if disallowed
2. Enforces per-host crawl delay (`wait_for_host`) — uses `Crawl-delay` from robots.txt or `scraper_min_delay_seconds` (default 2.0 s)
3. Uses an identifying User-Agent: `VoucherBot/0.1 (certification-voucher-aggregator; contact=<email>)`

`robots.txt` responses are cached per host for 1 hour.

---

## AI Service

**File:** `voucherbot/services/ai/analyzer.py`

### Provider chain

```
┌─ Groq llama-3.1-8b-instant    ─┐
├─ Groq openai/gpt-oss-120b     ─┼─► first success wins, siblings cancelled
└─ Groq llama-3.3-70b-versatile ─┘
          │ all Groq fail / daily-exhausted
          ▼
  Gemini gemini-2.5-flash   (final fallback only)
```

All three Groq models are called **concurrently**. The first successful response wins and the remaining calls are cancelled immediately. Gemini is only invoked if every Groq model fails or is daily-exhausted.

429 rate-limit errors are retried within the same provider (up to 3 attempts). Non-429 errors cause that model to return `None` without affecting its concurrent siblings.

### Rate limiting

Per-model sliding-window rate limiter tracks:
- Requests per minute (RPM)
- Tokens per minute (TPM) — estimated at `len(text) / 4 + 512`
- Tokens per day (TPD) and requests per day (RPD) — resets at UTC midnight

When a model hits its daily limit, `daily_exhausted = true` and it is skipped for the rest of the day.

A global `asyncio.Semaphore(4)` caps concurrent AI calls across all models to bound memory from in-flight prompt strings.

### Batch dispatch

`analyze_post_batch` distributes posts round-robin across available models using `asyncio.gather`. Each call acquires the global semaphore before making the provider request.

### Prompt

The system prompt instructs the model to set `is_voucher=true` on any promotional intent — even partial signals (no code required). It returns a strict JSON object matching the `ExtractedEvent` schema. Markdown fences in the response are stripped before parsing.

---

## Data Models

### sources

| Column | Type | Notes |
|--------|------|-------|
| id | integer PK | |
| name | string UNIQUE | e.g. `rss:aws_training_blog` |
| type | enum | REDDIT, RSS, BLOG, EVENT, FORUM, WEBSITE, API |
| base_url | string | |
| enabled | boolean | false = skip in scheduler |
| priority | integer | higher = processed first within tier |
| priority_tier | char(1) | A/B/C/D |
| config | JSONB | feed_url, selectors, poll_interval_minutes, etc. |
| next_due_at | timestamptz | scheduler target time |
| backoff_until | timestamptz | set on failure |
| consecutive_failures | integer | drives backoff exponent |
| avg_runtime_ms | integer | rolling average |
| error_count | integer | cumulative |
| last_checked_utc | timestamptz | |

### posts

| Column | Type | Notes |
|--------|------|-------|
| id | integer PK | |
| source_id | integer FK → sources | |
| external_id | string | identity_hash(url) |
| url | string | |
| title | string | |
| content | text | |
| status | enum | QUEUED → FILTERED or PROCESSED |
| score | integer | keyword score |
| ai_result | JSONB | full ExtractedEvent dump |
| content_hash | string(40) | SHA-256 of title+content+date |
| event_id | integer FK → events | NULL until EventMatcher runs |
| is_notified | boolean | true after email sent |

Unique constraint: `(source_id, external_id)`.

### events

| Column | Type | Notes |
|--------|------|-------|
| id | integer PK | |
| vendor | string | lower-cased |
| promotion_name | string | |
| promotion_type | string | voucher/discount/free_exam/bundle/beta_invite |
| certifications | JSONB | list[str] |
| voucher_code | string | upper-cased |
| discount | string | e.g. "50%" |
| registration_url | string | |
| start_date / end_date | timestamptz | |
| regions | JSONB | list[str] |
| status | enum | ACTIVE / EXPIRED / ARCHIVED |
| merge_log | JSONB | append-only audit trail |

### keywords

| Column | Type |
|--------|------|
| keyword | string UNIQUE |
| score | integer |
| enabled | boolean |

### pipeline_lock

| Column | Type |
|--------|------|
| name | string PK |
| holder | string |
| acquired_at | timestamptz |
| expires_at | timestamptz |

### voucher_posts (view)

Read-only view over `posts` where `ai_result->>'is_voucher' = 'true' AND status = 'PROCESSED'`. Flattens JSONB `ai_result` fields (`vendor`, `promotion_name`, `voucher_code`, `discount`, `registration_url`, `confidence`, `reason`) into columns. Served by `GET /alerts`.

---

## REST API

All routes are read-only. No authentication is implemented.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Returns `{"status": "ok"}` — no DB check |
| GET | `/ready` | Executes `SELECT 1` — 503 if DB unreachable |
| GET | `/sources` | List sources; filter by `type`, `enabled` |
| GET | `/posts` | List posts; filter by `status`, `source_type`, `min_score`; paginated |
| GET | `/alerts` | List AI-confirmed vouchers from `voucher_posts` view; filter by `notified`, `min_score` |

---

## Email Notifications

**Files:** `voucherbot/services/email/sender.py`, `voucherbot/services/email/notifications.py`

- Provider: Resend API (`resend` Python SDK)
- Throttle: `asyncio.Lock` + `email_min_interval_seconds` (default 5 s) between sends
- Email contains: vendor, promotion name, type, certifications, voucher code, discount, regions, dates, source post link, claim/register link
- Both HTML and plain-text bodies are sent
- `is_notified` is set to `true` on the post only after Resend confirms acceptance

---

## Database Access

**File:** `voucherbot/database/connection.py`

- Driver: `asyncpg` via `SQLAlchemy[asyncio]`
- Pool: `pool_size=2`, `max_overflow=3`, `pool_timeout=30`, `pool_recycle=240 s` (Supabase drops idle connections at ~300 s), `pool_pre_ping=True`
- Sessions: `async_sessionmaker` with `expire_on_commit=False`
- All ORM models use `Mapped` / `mapped_column` (SQLAlchemy 2.0 style)

---

## Schema Migrations

Managed by Alembic. Frozen at revision `g3b9c0d1e2f3`.

| Revision | Change |
|----------|--------|
| `ca84fdb8ee85` | Initial sources / posts / keywords schema |
| `a3f7c1d2e890` | Add events table + dedup fields |
| `b1f3e2a9d047` | Add `ai_result` JSONB to posts |
| `e1c2d3a4b5f6` | DB-driven scheduler fields on sources |
| `f2a8b9c0d1e2` | Add `is_notified`, create `voucher_posts` view |
| `g3b9c0d1e2f3` | Freeze: ensure keywords table in migration chain |

**Production rule:** With `IS_PROD=true`, the app uses a DML-only DB role. Schema changes must be applied by an admin via `alembic upgrade head` before deployment. The app never runs DDL in production.

---

## Configuration Reference

All settings are loaded from `.env` via `pydantic-settings`.

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | required | asyncpg connection string |
| `IS_PROD` | `false` | Skip DB init/bootstrap on startup |
| `LOG_LEVEL` | `INFO` | structlog level |
| `RESEND_API_KEY` | — | Email sending |
| `EMAIL_FROM` | `VoucherBot <onboarding@resend.dev>` | Sender address |
| `EMAIL_ID` | — | Recipient address for alerts |
| `EMAIL_MIN_INTERVAL_SECONDS` | `5.0` | Throttle between sends |
| `REDDIT_CLIENT_ID` | — | asyncpraw credentials |
| `REDDIT_CLIENT_SECRET` | — | asyncpraw credentials |
| `REDDIT_USER_AGENT` | — | asyncpraw credentials |
| `REDDIT_INGESTION_ENABLED` | `false` | Enable Reddit sources |
| `REDDIT_FETCH_LIMIT` | `25` | Posts per subreddit fetch |
| `GROQ_API_KEY` | — | Primary AI provider |
| `GROQ_REQUESTS_PER_MINUTE` | `30` | RPM cap |
| `GROQ_MAX_COMPLETION_TOKENS` | `1024` | Max tokens per response |
| `GROQ_MAX_INPUT_CHARS` | `12000` | Input truncation limit |
| `GEMINI_API_KEY` | — | Fallback AI provider |
| `SCRAPER_RESPECT_ROBOTS` | `true` | Obey robots.txt |
| `SCRAPER_MIN_DELAY_SECONDS` | `2.0` | Minimum per-host crawl delay |
| `SCRAPER_USER_AGENT` | — | Override default UA string |
| `TICK_LEASE_TTL_SECONDS` | `21600` | Pipeline lock TTL (6 h) |
| `SOURCE_BACKOFF_BASE_MINUTES` | `5` | Backoff base for failures |
| `SOURCE_BACKOFF_MAX_MINUTES` | `360` | Backoff ceiling (6 h) |

---

## Deployment

### Local (Docker)

```bash
cp .env.example .env
docker compose up --build
# API at http://localhost:8000
```

With `IS_PROD=false`, startup runs `init_db()` (create_all) and `bootstrap_data()` (seed sources + keywords).

### Production (Render)

Defined in `render.yaml`:
```yaml
buildCommand: pip install -e .
startCommand: uvicorn voucherbot.main:app --host 0.0.0.0 --port $PORT
```

Before first deploy:
1. Run `alembic upgrade head` with an admin DB role
2. Run bootstrap manually or via a one-off job
3. Set `IS_PROD=true` in environment

### Source catalog management

Sources are seeded from `voucherbot/database/bootstrap.py`. The catalog is config-driven — adding a new feed or page requires only a new entry in `SOURCE_DEFINITIONS` or `HIGH_SIGNAL_REDDIT_SUBREDDITS`; no schema migration needed.

Sources marked `unsupported: true` are inserted as `enabled=false` and skipped by all collectors. This documents policy-blocked sources (ToS, robots.txt) without removing them from the catalog.

Smoke-test all feeds/pages:
```bash
python scripts/verify_sources.py
```

---

## Key Design Decisions

**Single-process, sequential scheduling** — The scheduler processes one source at a time. This keeps CPU usage flat (< 0.1 vCPU) and avoids connection pool exhaustion. The tradeoff is that a slow source delays others; mitigated by `tick_job_timeout_seconds`.

**DB-driven scheduler state** — All scheduling fields (`next_due_at`, `backoff_until`, `consecutive_failures`) live in the `sources` table. On startup, all sources are reset to due (`next_due_at = NULL`). This means a restart always triggers a full sweep, which is intentional.

**Two-hash deduplication** — `identity_hash` (URL-based) provides stable identity across content changes. `content_hash` (content-based) detects updates to existing pages. Together they handle both "same page, new content" and "same content, different tracking URL" cases.

**Canonical Event deduplication** — Posts are never merged. Many posts from different sources can reference the same `Event` via FK. The Event holds the authoritative promotion data; posts provide provenance. The `merge_log` JSONB array is append-only and records every field update with source, score, and timestamp.

**AI provider fallback chain** — The system is not coupled to any single AI provider. Groq is primary (fast, generous free tier), Gemini is the final fallback. Provider selection is transparent to the pipeline — it only ever sees `ExtractedEvent`.

**robots.txt compliance** — All HTTP requests go through `polite_get`. Sources that violate ToS or are blocked by robots.txt are marked `unsupported` in the catalog and skipped at the collector level, not at the HTTP level, to avoid wasting a request.
