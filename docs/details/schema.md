# Database schema (frozen)

**Frozen revision:** `g3b9c0d1e2f3`  
Apply with: `alembic upgrade head`

Do not add or alter tables for Reddit enablement — Reddit uses existing `sources` / `posts`. New schema work requires a new Alembic revision and an explicit un-freeze decision.

## Objects

| Object | Type | Purpose |
|--------|------|---------|
| `sources` | table | Feeds, pages, subreddits + scheduler fields |
| `posts` | table | Ingested items, `ai_result`, `is_notified`, `event_id` |
| `events` | table | Canonical promotions |
| `keywords` | table | Keyword scoring catalog |
| `pipeline_lock` | table | Dispatcher lease |
| `alembic_version` | table | Migration pointer |
| `voucher_posts` | **view** | AI-confirmed vouchers only (`is_voucher` + `PROCESSED`) |

## Enums

- `sourcetype`, `poststatus`, `eventstatus`

## Prod rule

With `IS_PROD=true`, the app must not run DDL. Schema changes are admin-only via Alembic.
