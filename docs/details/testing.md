# 🧪 Testing

This project uses **pytest** for unit and integration testing.

---

## 📋 Table of Contents

1. [Prerequisites](#-prerequisites)
2. [Configure the Environment](#️-configure-the-environment)
3. [Install Development Dependencies](#-install-development-dependencies)
4. [Running the Test Suite](#-running-the-test-suite)
5. [Understanding the Results](#-understanding-the-results)
6. [Troubleshooting](#-troubleshooting)

---

## 🧰 Prerequisites

Before running the test suite, create and activate the project's virtual environment.

### Windows (PowerShell)

Create the virtual environment:

```powershell
python -m venv .venv
```

Activate it:

```powershell
.venv\Scripts\Activate.ps1
```

### Linux / macOS

Create the virtual environment:

```bash
python3 -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

---

## ⚙️ Configure the Environment

This project requires several environment variables for configuration.

A template is provided as `.env.example`.

1. Copy the template:

   ```bash
   cp .env.example .env
   ```

   **Windows (PowerShell):**

   ```powershell
   Copy-Item .env.example .env
   ```

2. Open `.env` and replace all placeholder values with real configuration values.

   This includes any required database connection strings, email credentials, API keys, and (optionally) Reddit API credentials.

   > **📝 Note:** Reddit-related tests require valid Reddit API credentials. If these values are left blank, the Reddit test(s) are expected to fail.

---

## 📦 Install Development Dependencies

Install the project together with all development dependencies:

```bash
pip install -e ".[dev]"
```

This installs the project in editable mode and includes development tools such as:

- pytest
- pytest-asyncio
- ruff
- mypy

---

## ▶️ Running the Test Suite

Run all tests:

```bash
pytest
```

or

```bash
python -m pytest
```

For more verbose output:

```bash
pytest -v
```

---

## 📊 Understanding the Results

A typical test run will produce output similar to:

```text
107 passed
15 skipped
```

### ✅ Passed

Passed tests completed successfully.

### ⏭️ Skipped

Skipped tests are **intentional** and are **not failures**.

Some collector tests only apply to a particular collector type.

For example:

- RSS validation tests skip sources that are implemented as website scrapers.
- Website scraping tests skip sources that are implemented using RSS feeds.

This confirms that the correct collector is configured for each source rather than indicating a problem.

The deduplication suite also includes URL canonicalization checks that verify tracking parameters are removed and host matching is parsed safely rather than relying on substring checks.

### ❌ Failed

A failed test indicates that the implementation does not currently match the expected behaviour or that an optional external dependency has not been configured.

The project supports collecting voucher information from Reddit, which requires Reddit API credentials. These credentials are intentionally **not** included in the repository.

If Reddit API credentials are not configured in your `.env` file, the Reddit-related test will fail. This is expected behaviour and does not indicate an issue with the rest of the application.

To run the complete test suite successfully, populate the Reddit configuration values in `.env` with valid API credentials obtained from Reddit's developer portal.

Without Reddit credentials, all other tests should still pass successfully.


## 🧪 Testing the AI Voucher Parser End-to-End

The project includes a **local test source** that lets you verify the full pipeline — scraping, keyword filtering, AI extraction, and notification — without relying on real external feeds.

### 1. Configure the Environment

Set the following in your `.env` file:

```env
IS_TEST=true
IS_PROD=false
```

- `IS_TEST=true` — seeds a `website:local_test` source pointing at `http://localhost:35926/` (see `voucherbot/database/bootstrap.py:928-945`)
- `IS_PROD=false` — the app creates tables and runs bootstrap on startup

### 2. Start the Local Test Server

The test server is a minimal HTTP server at `D:\components\server.py` that serves:

| Route | Content |
|-------|---------|
| `GET /` | `index.html` — scraped by the WebsiteCollector |
| `GET /api/items` | `items.json` — test data payload |
| `POST /api/items` | Update test data |

**Start it from the `D:\components\` directory:**

```powershell
cd D:\components
python server.py
```

The server listens on `http://localhost:35926/`.

### 3. How the Scraper Works

The test source is defined at **`voucherbot/database/bootstrap.py:928-945`**:

```python
"config": {
    "url": "http://localhost:35926/",
    "vendor": "local_test",
    "article_selector": ".item",     # each item <div>
    "title_selector": "h2",          # title inside .item
    "link_selector": "self",         # no link extraction
    "query_terms": [...],            # keywords for filtering
    "poll_interval_minutes": 5,
}
```

The `WebsiteCollector` (`voucherbot/providers/website/collector.py:37-41`) reads these selectors and scrapes the page using BeautifulSoup.

The `index.html` at `D:\components\index.html` contains `.item` divs with `<h2>` titles — this structure matches the default selectors. **To test different content, edit the HTML or the selectors.**

### 4. Customising Test Data

Edit **`D:\components\items.json`** to control what the API returns. Default content:

```json
[
  {
    "title": "free voucher",
    "description": "free test voucher for localhost"
  }
]
```

The scraper parses the rendered HTML page (`/`), *not* the JSON API directly. The API is available if you want to build dynamic test pages.

### 5. Running the Test

Start the main app (keep the test server running in another terminal):

```powershell
uvicorn voucherbot.main:app --host 0.0.0.0 --port 9000
```

On startup the app:

1. Creates tables and seeds data (including the `website:local_test` source)
2. The scheduler picks up the source and runs the pipeline
3. The `WebsiteCollector` fetches `http://localhost:35926/` and extracts `.item` elements
4. Keyword filtering scores each post against your `query_terms`
5. AI extraction analyses matching posts
6. If a voucher is detected, a notification is sent

### 6. Watching the Pipeline

Monitor the server logs. A successful test run produces output like:

```
WebsiteCollector: fetching       url=http://localhost:35926/
WebsiteCollector: collected      url=http://localhost:35926/  count=1
pipeline: keyword filter         fetched=1 filtered=0 passed=1  source=website:local_test
pipeline: AI analysis            posts=1 ...
dispatcher: tick ran             source=website:local_test  ...
```

### 7. Modifying Scraping Behaviour

To change how the test page is parsed, edit:

| File | Lines | What to change |
|------|-------|----------------|
| `voucherbot/database/bootstrap.py` | 928-945 | Source config (`article_selector`, `title_selector`, `link_selector`, `query_terms`) |
| `voucherbot/providers/website/collector.py` | 37-41 | Default selector fallbacks |
| `voucherbot/config/settings.py` | 68 | `is_test` setting |

After changing source config, restart the app so bootstrap re-upserts the source.

---

### 🔧 Troubleshooting

### `pytest: command not found`

Development dependencies have not been installed.

Run:

```bash
pip install -e ".[dev]"
```

---

### `Unknown pytest.mark.asyncio`

`pytest-asyncio` has not been installed.

Install the development dependencies:

```bash
pip install -e ".[dev]"
```

---

### Missing Environment Variables

If tests fail during startup because configuration values (such as `DATABASE_URL`) are missing:

- ensure `.env` exists,
- ensure it was created from `.env.example`,
- replace all placeholder values with valid configuration values,
- run the tests from the project root.