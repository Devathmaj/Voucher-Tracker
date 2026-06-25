# VoucherBot

Certification voucher aggregator — collects from RSS, vendor blogs, event pages, and Reddit; filters by keywords; uses AI to extract promotions.

## Local Setup

1. Copy `.env.example` to `.env`.
2. Run `docker compose up --build`.
3. The API will be available at `http://localhost:8000`.

## Source catalog

Official sources are documented in [`sources/`](sources/) and seeded via [`voucherbot/database/bootstrap.py`](voucherbot/database/bootstrap.py) on startup.

```bash
python scripts/verify_sources.py   # smoke-test feed/page collectors
```
