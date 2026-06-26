# VoucherBot

Certification voucher aggregator — collects from RSS, vendor blogs, event pages, and Reddit; filters by keywords; uses AI to extract promotions.

## Local Setup

1. Copy `.env.example` to `.env`.
2. Run `docker compose up --build`.
3. The API will be available at `http://localhost:8000`.

With `IS_PROD=false`, startup creates missing tables and seeds sources/keywords. With `IS_PROD=true`, that is skipped — apply schema via `alembic upgrade head` (admin role) before deploying; the app role should only need DML on existing tables.

## Source catalog

Official sources are documented in [`sources/`](sources/) and seeded via [`voucherbot/database/bootstrap.py`](voucherbot/database/bootstrap.py) when `IS_PROD=false`.

```bash
python scripts/verify_sources.py   # smoke-test feed/page collectors
```
