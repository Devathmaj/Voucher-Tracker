# Database schema

**Current revision:** `j0k1l2m3n4o5`  
Apply with: `alembic upgrade head`

## Objects

| Object | Type | Purpose |
|--------|------|---------|
| `sources` | table | Feeds, pages, subreddits + scheduler fields |
| `posts` | table | Ingested items, `vendor`, `ai_result`, `is_notified`, `event_id` |
| `events` | table | Canonical promotions |
| `keywords` | table | Keyword scoring catalog |
| `vendor_mappings` | table | URL/source-name pattern → vendor lookup |
| `pipeline_lock` | table | Dispatcher lease |
| `alembic_version` | table | Migration pointer |
| `voucher_posts` | **view** | AI-confirmed vouchers only (`is_voucher` + `PROCESSED`) |

## Enums

- `sourcetype`, `poststatus`, `eventstatus`

## Prod rule

With `IS_PROD=true`, the app must not run DDL. Schema changes are admin-only via Alembic.
