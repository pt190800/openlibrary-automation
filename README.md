# OpenLibrary Automation

E2E test automation framework for [openlibrary.org](https://openlibrary.org) — book search with year filtering, reading list management, and page performance measurement.

Built with **Python + Playwright**, Page Object Model (POM) architecture, data-driven testing via JSON, and full Allure + HTML reporting.

---

## Architecture

### Directory structure

```
openlibrary_automation/
├── config/
│   ├── settings.py              # Loads test_data.json → exports BASE_URL + CFG
│   └── test_data.json           # All test inputs: queries, thresholds, profiles
│
├── pages/                       # Page Object Model — one class per page
│   ├── base_page.py             # BasePage: navigation, backoff, mouse, screenshots
│   ├── search_page.py           # SearchPage: search, pagination, year filtering
│   ├── book_page.py             # BookPage: add to reading list, session/CAPTCHA checks
│   └── reading_list_page.py     # ReadingListPage: open list, count books across pages
│
├── utils/
│   ├── flows.py                 # LibraryFlows: orchestrates all E2E flows
│   └── performance.py           # PerformanceReporter: time-to-element + JSON report
│
├── tests/
│   ├── conftest.py              # Fixtures (page, auth_page), hooks, stealth browser setup
│   └── test_openlibrary.py      # TestAuth, TestSearch, TestReadingList, TestPerformance
│
├── screenshots/                 # Auto-created: per-book + failure screenshots
├── reports/
│   ├── allure-results/          # Allure raw output
│   └── traces/                  # Playwright trace .zip per test
│
├── performance_report.json      # Auto-generated: page load metrics
├── save_session.py              # Opens real browser for manual login → saves session.json
├── .env / .env.example          # Credentials — only needed for TestAuth
├── session.json                 # Created by save_session.py — not committed
└── requirements.txt
```

---

### Class hierarchy

```
BasePage
├── SearchPage        search, paginate, year-filter, collect URLs
├── BookPage          add to reading list, dropdown, auth/CAPTCHA guard
└── ReadingListPage   open /account/books/want-to-read, count items

LibraryFlows          orchestrates all three page objects (not a page)
PerformanceReporter   standalone: time-to-element, browser metrics, JSON save
```

---

### Class responsibilities

#### `BasePage` — [pages/base_page.py](pages/base_page.py)

Base class inherited by all page objects. Centralises cross-cutting concerns.

| Method | What it does |
|--------|-------------|
| `navigate(url)` | `page.goto` with exponential backoff on HTTP 429 and connection resets (5s → 10s → 20s → 40s ± 2s jitter, 4 attempts) |
| `_human_mouse_move(steps)` | Moves mouse through `steps` random intermediate points with overshoot — mimics organic hand movement |
| `_human_click(selector)` | Waits for element visibility, approaches from a random offset, then clicks |
| `_delay(kind)` | `wait_for_timeout` with randomised range per `kind`: navigate 800–1800ms, pagination 1500–2500ms, action 1000–2000ms, login 2000–3000ms |
| `take_screenshot(name)` | Saves PNG to `screenshots/`, sanitises filename, swallows errors (test never fails due to screenshot) |

---

#### `SearchPage` — [pages/search_page.py](pages/search_page.py)

Handles the OpenLibrary search results page.

**Selectors:**

| Constant | Value |
|----------|-------|
| `SEARCH_INPUT` | `input[name='q']` |
| `SEARCH_BUTTON` | `button[type='submit']` |
| `RESULT_ITEMS` | `li.searchResultItem` |
| `BOOK_YEAR` | `span.resultDetails` |
| `BOOK_LINK` | `a[href*='/works/']` |
| `NEXT_PAGE` | `a[title='next page'], a[aria-label='Next Page']` (composite — catches both label variants) |

**Methods:**

| Method | What it does |
|--------|-------------|
| `search(query)` | Fill input → click submit → wait for `domcontentloaded` |
| `get_result_items()` | Returns all `li.searchResultItem` handles on the current page |
| `has_next_page()` | Checks if `NEXT_PAGE` selector exists |
| `go_to_next_page()` | Click next → wait for load → pagination delay |
| `_extract_year(text)` | Static method: regex `\b(1[0-9]{3}\|20[012][0-9])\b` on the "First published in XXXX" string — robust against extra text |
| `collect_urls_under_year(max_year, limit)` | Core loop: iterate results → parse year → filter → collect href → paginate until `limit` reached or no more pages |

---

#### `BookPage` — [pages/book_page.py](pages/book_page.py)

Handles an individual book's works page on OpenLibrary.

**Selectors:**

| Constant | Value |
|----------|-------|
| `READY_SELECTOR` | `h1` |
| `PRIMARY_BTN` | `button.book-progress-btn.primary-action` |
| `DROPDOWN_TOGGLE` | `a.generic-dropper__dropclick` |
| `WANT_TO_READ_BTN` | `div.read-statuses button:has-text('Want to Read')` |
| `ALREADY_READ_BTN` | `div.read-statuses button:has-text('Already Read')` |
| `CURRENTLY_READING_BTN` | `div.read-statuses button:has-text('Currently Reading')` |

**Methods:**

| Method | What it does |
|--------|-------------|
| `_assert_authenticated()` | Checks current URL and DOM for `/account/login` redirect, `#username` form, CAPTCHA iframes — raises `RuntimeError` with recovery hint on any failure |
| `_is_unactivated()` | Returns `True` if `PRIMARY_BTN` has class `unactivated` (book not yet in any reading list) |
| `_click_via_dropdown(selector)` | Opens dropdown via `DROPDOWN_TOGGLE`, waits for dropdown to expose `selector`, clicks it; returns `False` if dropdown didn't open |
| `add_to_reading_list()` | Calls `_assert_authenticated()` → skips if already listed → randomly picks "Want to Read" (primary button click) or "Already Read" (dropdown path) → falls back to primary if dropdown fails → returns action string |

---

#### `ReadingListPage` — [pages/reading_list_page.py](pages/reading_list_page.py)

Handles `/account/books/want-to-read`.

| Method | What it does |
|--------|-------------|
| `open()` | Navigates to the want-to-read page via `BasePage.navigate()` |
| `get_book_count()` | Counts `li.searchResultItem` items across **all pages** via pagination loop — returns total |

---

#### `LibraryFlows` — [utils/flows.py](utils/flows.py)

Orchestrator class — uses all three page objects to implement the three core E2E flows. Not a page object itself; holds a `Page` reference and constructs page objects per call.

| Method | Allure step | What it does |
|--------|-------------|-------------|
| `search_books_by_title_under_year(query, max_year, limit)` | ✓ | Creates `SearchPage`, navigates to `/search?q={query}`, calls `collect_urls_under_year` |
| `_assert_session()` | — | Navigates to want-to-read page; raises if redirected to login |
| `add_books_to_reading_list(urls)` | ✓ | `_assert_session()` → per URL: navigate, `add_to_reading_list()`, screenshot, Allure attach; returns count of "Want to Read" adds only |
| `get_reading_list_count()` | ✓ | `_assert_session()` → `ReadingListPage.get_book_count()` |
| `assert_reading_list_count(expected)` | ✓ | Opens list, counts, takes screenshot, asserts `actual == expected` |

---

#### `PerformanceReporter` — [utils/performance.py](utils/performance.py)

Standalone utility for page load measurement.

| Method / Property | What it does |
|-------------------|-------------|
| `measure(url, threshold_ms, selector)` | `page.goto(url)` → `wait_for_selector(state="attached")` → `time.monotonic()` → `page.evaluate(JS)` for browser Navigation Timing API metrics; retries 3× with 15s/30s/45s backoff; logs warning if `load_time_ms > threshold_ms` (never fails test) |
| `save()` | Writes `performance_report.json` (pretty-printed, UTF-8) |
| `results` | Property — returns copy of collected metrics list |

**Metrics collected per URL:**

| Field | Source |
|-------|--------|
| `time_to_element_ms` | `time.monotonic()` from navigation start to selector attached |
| `load_time_ms` | `performance.getEntriesByType('navigation')[0].loadEventEnd` |
| `dom_content_loaded_ms` | `performance.getEntriesByType('navigation')[0].domContentLoadedEventEnd` |
| `first_paint_ms` | `performance.getEntriesByType('paint')` → `'first-paint'` entry |
| `threshold_ms` | Passed in from `test_data.json` |
| `timestamp` | `datetime.now().isoformat()` |

---

### Test classes — [tests/test_openlibrary.py](tests/test_openlibrary.py)

| Class | Fixture | Tests | Allure feature |
|-------|---------|-------|----------------|
| `TestAuth` | `page` | `test_login` — full login flow with verify_human handling | Authentication |
| `TestSearch` | `page` | `test_search_returns_list`, `test_search_no_results`, `test_parametrized_search[data0/1]` | Search |
| `TestReadingList` | `auth_page` | `test_full_flow` — search → count before → add → assert delta | Reading List |
| `TestPerformance` | `page` | `test_performance` — 3 pages measured against thresholds | Performance |

`TestAuth` is excluded from the default run via `pytest.mark.auth` and `addopts = -m "not auth"`.

---

### Fixtures & hooks — [tests/conftest.py](tests/conftest.py)

#### `page` fixture
Stealth Chromium context (no session), tracing enabled. Cleaned up with trace zip on teardown.

#### `auth_page` fixture
Tries `session.json` first; if absent, logs in with `.env` credentials including `verify_human` page handling. Same stealth context and trace lifecycle as `page`.

#### Stealth browser config

| Setting | Value |
|---------|-------|
| User-Agent | `Chrome/124.0.0.0` (Linux x86_64) |
| Init script | Removes `navigator.webdriver`, fakes `plugins` + `languages`, injects `chrome.runtime` |
| Launch args | `--disable-blink-features=AutomationControlled`, `--no-sandbox`, `--disable-dev-shm-usage`, `--window-size=1920,1080`, `--disable-gpu` |
| Viewport | 1920 × 1080 |
| Tracing | screenshots + snapshots + sources per test |

#### `pytest_runtest_setup` hook
Sleeps `random.uniform(8, 14)` seconds before every test except `TestPerformance` — prevents HTTP 429 from burst requests.

#### `pytest_runtest_makereport` hook
On test failure: captures full-page screenshot, current URL + title, console errors, HTML snapshot — attaches all to Allure.

---

### E2E data flow

```
test_data.json
      │
      ▼
config/settings.py  ──► BASE_URL, CFG
      │
      ▼
LibraryFlows (flows.py)
      │
      ├──► SearchPage.collect_urls_under_year(query, max_year, limit)
      │         └── paginate results, regex year, collect /works/ hrefs
      │
      ├──► BookPage.add_to_reading_list()   (per URL)
      │         ├── _assert_authenticated()
      │         ├── _is_unactivated()
      │         └── random: Want to Read (primary) | Already Read (dropdown)
      │
      └──► ReadingListPage.get_book_count()
                └── paginate want-to-read page, sum li.searchResultItem

Test assertion:  actual == count_before + want_to_read_count
```

---

## Prerequisites

| Tool | Minimum version | Check |
|------|----------------|-------|
| Python | 3.10+ | `python3 --version` |
| Node.js + npm | 16+ | `node --version` |
| Java JRE | 11+ | `java -version` |

---

## Setup

### 1 — Create and activate a virtual environment

Ubuntu 24.04+ blocks system-wide pip installs — use a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

> **Re-activate before every session:** `source venv/bin/activate`  
> Your prompt will show `(venv)` when the environment is active.

### 2 — Install Python dependencies

```bash
pip install -r requirements.txt
```

Installs: `playwright`, `pytest`, `pytest-asyncio`, `allure-pytest`, `pytest-html`, `python-dotenv`

### 3 — Install Chromium

```bash
playwright install chromium
```

### 4 — Install Java (required for Allure)

```bash
sudo apt install default-jre -y
```

### 5 — Install Allure CLI

```bash
npm install -g allure-commandline
```

### 6 — Save your session (required for reading list tests)

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

`TestAuth` tests the full login flow (navigate → fill → submit → verify_human → assert).  
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

## Data-Driven

All test inputs live in `config/test_data.json` — change without touching code:

```json
{
  "searches": [
    { "query": "Dune", "max_year": 1980, "limit": 5 },
    { "query": "Lord of the Rings", "max_year": 1970, "limit": 3 }
  ],
  "performance_thresholds": {
    "search_page": 3000,
    "book_page": 2500,
    "reading_list": 2000
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
| HTTP 429 (rate limit) | Exponential backoff: 5s → 10s → 20s → 40s ± 2s jitter (4 attempts) |
| Bot detection | Human mouse movement — random paths with overshoot before every click |
| Session expiry | `_assert_session()` + `_assert_authenticated()` before every action |
| Already-listed books | `unactivated` class check on primary button — skips books already in any list |
| Performance measurement | `wait_for_selector(state="attached")` + `time.monotonic()` — unaffected by external resources |
| Hidden buttons | `_is_unactivated()` check — opens dropdown path instead of direct click |
| CAPTCHA | Selector detection (4 selectors) → `RuntimeError` with clear recovery hint |
| Too-fast runs | `random.uniform(8, 14)` sleep before each test via `pytest_runtest_setup` hook |
| Invalid filename | `re.sub(r"[^a-zA-Z0-9_-]", "_", name)[:120]` before every screenshot save |
| Screenshot hang | `timeout=10000` + try/except — test never fails due to screenshot issue |
| Burst retries | 3-attempt retry with 15s/30s/45s backoff inside `PerformanceReporter.measure()` |

---

## Known Limitations

- **CAPTCHA** — If OpenLibrary detects unusual traffic, it shows a human verification page. Wait 10–15 minutes between runs.
- **Reading list cleanup** — Tests do not delete added books. Repeated runs use delta-based assertion (before/after count).
- **Selectors** — CSS classes on the site may change with OpenLibrary updates.
- **Headless mode** — Tests run headless (no browser window). This may increase CAPTCHA frequency on OpenLibrary.
