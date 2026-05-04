# OpenLibrary Automation

E2E test automation framework for [openlibrary.org](https://openlibrary.org) — book search, reading list management, and performance measurement.

Built with **Python + Playwright**, Page Object Model architecture, data-driven testing from JSON, and Allure reports.

---

## Prerequisites

| Tool | Minimum version | Check |
|------|----------------|-------|
| Python | 3.10+ | `python3 --version` |
| Node.js + npm | 16+ | `node --version` |
| Java JRE | 11+ | `java -version` |

---

## Setup

### 1 — Install Python dependencies

```bash
pip install -r requirements.txt
```

Installs: `playwright`, `pytest`, `pytest-asyncio`, `allure-pytest`, `pytest-html`, `python-dotenv`

### 2 — Install Chromium

```bash
playwright install chromium
```

### 3 — Install Java (required for Allure)

```bash
sudo apt install default-jre -y
```

### 4 — Install Allure CLI

```bash
npm install -g allure-commandline
```

### 5 — Save your session (required for reading list tests)

```bash
python3 save_session.py
```

Opens a browser window — log in manually (fill email + password, solve CAPTCHA if it appears).  
The session is saved automatically to `session.json` once a successful login is detected.

> **Run this once before running the tests.** Tests use `session.json` on every run.  
> If the session expires (usually after a few days) — run it again.

---

## Running the Tests

```bash
pytest
```

| Command | What runs | Requires |
|---------|-----------|----------|
| `pytest` | 6 tests (search + reading list + performance) | `session.json` |
| `pytest -k TestSearch` | 4 search tests | nothing |
| `pytest -k TestPerformance` | page load timing | nothing |
| `pytest -k TestReadingList` | full E2E flow | `session.json` |
| `TEST_PROFILE=quick pytest -k TestReadingList` | quick flow — 3 books | `session.json` |
| `pytest -m auth` | login flow test | `.env` with credentials |

> **Wait 5–10 minutes between full runs** — OpenLibrary rate-limits requests (HTTP 429).

---

## Expected Output

```
tests/test_openlibrary.py::TestSearch::test_search_returns_list        PASSED
tests/test_openlibrary.py::TestSearch::test_search_no_results          PASSED
tests/test_openlibrary.py::TestSearch::test_parametrized_search[data0] PASSED
tests/test_openlibrary.py::TestSearch::test_parametrized_search[data1] PASSED
tests/test_openlibrary.py::TestReadingList::test_full_flow              PASSED
tests/test_openlibrary.py::TestPerformance::test_performance           PASSED

6 passed in ~3 minutes
```

**Auto-generated files:**
- `screenshots/` — screenshot per book added + failure screenshots
- `reports/allure-results/` — Allure data
- `reports/report.html` — self-contained HTML report (open directly in browser)
- `reports/traces/*.zip` — Playwright Trace per test
- `performance_report.json` — page load timing results

---

## Reports

### Allure Report

```bash
allure serve reports/allure-results
```

Opens a browser with a full visual report: features, stories, steps, screenshots, attachments.

### Playwright Trace Viewer

```bash
npx playwright show-trace reports/traces/tests_test_openlibrary_py__TestReadingList__test_full_flow.zip
```

Shows a full timeline of the test: every action, screenshot, network request, and error.

---

## Optional: Login Flow Test (TestAuth)

`TestAuth` tests the full login flow (navigate → fill → submit → assert).  
It is excluded from the default `pytest` run and requires credentials in `.env`.

### Setup credentials

```bash
cp .env.example .env
```

Edit `.env`:
```
OL_USERNAME=your_openlibrary_email
OL_PASSWORD=your_password
```

### Run

```bash
pytest -m auth
```

> **Note:** OpenLibrary frequently shows CAPTCHA on automated login.  
> If the test skips — that's a site-side limitation, not a code bug.  
> Use `save_session.py` for reliable authenticated testing.

---

## Architecture

```
openlibrary_automation/
├── config/
│   └── test_data.json           # Data-driven inputs: queries, thresholds, profiles
├── pages/                       # Page Object Model
│   ├── base_page.py             # Navigation + exponential backoff + human mouse + screenshots
│   ├── search_page.py           # Search + pagination + publication year regex
│   ├── book_page.py             # Reading list buttons + session/CAPTCHA detection
│   └── reading_list_page.py     # Open list + count books
├── utils/
│   ├── flows.py                 # LibraryFlows — all E2E flows in one class
│   └── performance.py           # PerformanceReporter — time-to-element + JSON output
├── tests/
│   ├── conftest.py              # Fixtures: page, auth_page + tracing + failure hook
│   └── test_openlibrary.py      # TestSearch, TestReadingList, TestPerformance, TestAuth
├── screenshots/                 # Auto-created
├── reports/
│   ├── allure-results/          # Allure output
│   └── traces/                  # Playwright traces (.zip)
├── performance_report.json      # Auto-created
├── save_session.py              # Manual login + session.json save
├── .env / .env.example          # Credentials — optional, only needed for TestAuth
├── session.json                 # Created by save_session.py — not committed to Git
└── requirements.txt
```

### Class responsibilities

| Class | Inherits | Responsibility |
|-------|----------|----------------|
| `BasePage` | — | Navigation, backoff, human mouse movement, screenshots, delays |
| `SearchPage` | `BasePage` | Search, pagination, publication year filtering |
| `BookPage` | `BasePage` | Reading list button clicks, dropdown, session/CAPTCHA detection |
| `ReadingListPage` | `BasePage` | Open list and count items |
| `LibraryFlows` | — | Orchestrates E2E flows: search, add to list, assertion |
| `PerformanceReporter` | — | Measures time-to-element, aggregates results, saves JSON |

---

## Data-Driven

All test inputs live in `config/test_data.json` — change without touching code:

```json
{
  "searches": [
    { "query": "Dune", "max_year": 1980, "limit": 5 },
    { "query": "Lord of the Rings", "max_year": 1970, "limit": 3 }
  ],
  "performance_thresholds": {
    "search_page": 8000,
    "book_page": 6000,
    "reading_list": 5000
  },
  "known_book_path": "/works/OL27448W",
  "profiles": {
    "quick": { "query": "Dune", "max_year": 1980, "limit": 3 },
    "full":  { "query": "Dune", "max_year": 1980, "limit": 5 }
  }
}
```

Profile selected via `TEST_PROFILE=quick` / `TEST_PROFILE=full` (default: `full`).

---

## Reliability Mechanisms

| Problem | Solution |
|---------|----------|
| HTTP 429 (rate limit) | Exponential backoff: 5s → 10s → 20s → 40s |
| Bot detection | Human mouse movement — random paths + overshoot before every click |
| Session expiry | `_assert_session()` + `_assert_authenticated()` before every action |
| Already-listed books | `unactivated` class check — skips books already in any reading list |
| Performance measurement | `wait_for_selector(state="attached")` + `time.monotonic()` — unaffected by external resources |
| Hidden buttons | `is_visible()` + `unactivated` class check before clicking |
| CAPTCHA | Selector detection + clear `RuntimeError` + screenshot |
| Too-fast runs | Random 8–14s delay between tests (`pytest_runtest_setup`) |
| Invalid filename | `re.sub` to sanitize characters before saving screenshot |
| Screenshot hang | `timeout=10000` + try/except — test never fails due to screenshot issue |

---

## Known Limitations

- **CAPTCHA** — If OpenLibrary detects unusual traffic, it shows a human verification page. Wait 10–15 minutes between runs.
- **Reading list cleanup** — Tests do not delete added books. Repeated runs use delta-based assertion (before/after count).
- **Selectors** — CSS classes on the site may change with OpenLibrary updates.
- **headless=False** — Intentional; headless mode significantly increases CAPTCHA frequency.
