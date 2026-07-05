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
106 passed
15 skipped
1 failed
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

### ❌ Failed

A failed test indicates that the implementation does not currently match the expected behaviour or that an optional external dependency has not been configured.

At the time of writing, the only expected failure is related to the Reddit integration.

The project supports collecting voucher information from Reddit, which requires Reddit API credentials. These credentials are intentionally **not** included in the repository.

If Reddit API credentials are not configured in your `.env` file, the Reddit-related test will fail. This is expected behaviour and does not indicate an issue with the rest of the application.

To run the complete test suite successfully, populate the Reddit configuration values in `.env` with valid API credentials obtained from Reddit's developer portal.

Without Reddit credentials, all other tests should still pass successfully.

---

## 🔧 Troubleshooting

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