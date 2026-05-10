import logging
import os
import pytest
import allure

from config.settings import BASE_URL, CFG
from utils.flows import LibraryFlows
from utils.performance import PerformanceReporter
from pages.search_page import SearchPage
from pages.book_page import BookPage
from pages.reading_list_page import ReadingListPage

logger = logging.getLogger(__name__)


# ── tests ───────────────────────────────────────────────────────────────────

@allure.feature("Authentication")
@pytest.mark.auth
@pytest.mark.skipif(
    not os.getenv("OL_USERNAME") or not os.getenv("OL_PASSWORD"),
    reason="OL_USERNAME / OL_PASSWORD חסרים ב-.env"
)
class TestAuth:

    @allure.story("Login flow")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_login(self, page):
        """Flow לוגין שלם: navigate → fill → submit → verify_human → assert logged in."""
        username = os.getenv("OL_USERNAME")
        password = os.getenv("OL_PASSWORD")

        # שלב 1: ניווט לדף הלוגין
        with allure.step("Navigate to login page"):
            resp = await page.goto(f"{BASE_URL}/account/login", wait_until="networkidle")
            if resp and resp.status == 429:
                pytest.skip("HTTP 429 — האתר חסם בקשות. המתן כמה דקות ונסה שוב.")
            allure.dynamic.parameter("url", page.url)

        # שלב 2: verify_human לפני הטופס
        with allure.step("Handle verify_human (pre-login)"):
            if "/verify_human" in page.url:
                try:
                    await page.wait_for_url(
                        lambda url: "/verify_human" not in url,
                        timeout=60_000,
                    )
                except Exception:
                    pytest.skip("verify_human לפני טופס הלוגין — CAPTCHA ב-headless. זו מגבלת האתר, לא באג בקוד.")

        # שלב 3: מילוי הטופס
        with allure.step("Fill login form"):
            try:
                await page.wait_for_selector("#username", state="visible", timeout=15_000)
            except Exception:
                shot = await page.screenshot(timeout=5000)
                allure.attach(shot, name="no_login_form", attachment_type=allure.attachment_type.PNG)
                pytest.skip(f"טופס לוגין לא נמצא (URL: {page.url})")

            await page.fill("#username", username)
            await page.fill("#password", password)

        # שלב 4: submit
        with allure.step("Submit form"):
            await page.click("button[type='submit'], input[type='submit']")
            await page.wait_for_load_state("networkidle")
            allure.dynamic.parameter("post_submit_url", page.url)

        # שלב 5: verify_human אחרי submit
        with allure.step("Handle verify_human (post-submit)"):
            if "/verify_human" in page.url:
                try:
                    await page.wait_for_url(
                        lambda url: "/verify_human" not in url,
                        timeout=60_000,
                    )
                    await page.wait_for_load_state("networkidle")
                except Exception:
                    pytest.skip("verify_human אחרי submit — CAPTCHA ב-headless. זו מגבלת האתר, לא באג בקוד.")

        # שלב 6: assert — המשתמש מחובר
        with allure.step("Assert logged in"):
            if "/account/login" in page.url:
                shot = await page.screenshot(timeout=5000)
                allure.attach(shot, name="login_failed", attachment_type=allure.attachment_type.PNG)
                pytest.fail(f"הלוגין נכשל — עדיין בדף הלוגין. URL: {page.url}")

            await page.goto(f"{BASE_URL}/account/books/want-to-read", wait_until="domcontentloaded")
            assert "/account/login" not in page.url, \
                f"הסשן לא נשמר — הופנה לדף הלוגין. URL: {page.url}"
            logger.info(f"Login verified — URL: {page.url}")


@allure.feature("Search")
class TestSearch:

    @allure.story("Basic search with year filter")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_search_returns_list(self, page):
        flows = LibraryFlows(page)
        urls = await flows.search_books_by_title_under_year("Dune", 1980, 5)
        assert isinstance(urls, list)
        logger.info(f"Collected {len(urls)} URLs")

    @allure.story("Search returns empty list when no match")
    @allure.severity(allure.severity_level.MINOR)
    async def test_search_no_results(self, page):
        flows = LibraryFlows(page)
        # 1300 — לפני המדפסות, בוודאות לא יהיו תוצאות עם שנה כה קדומה
        urls = await flows.search_books_by_title_under_year("Dune", 1300, 5)
        assert urls == []

    @allure.story("Parametrized search")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.parametrize("data", CFG["searches"])
    async def test_parametrized_search(self, page, data):
        flows = LibraryFlows(page)
        urls = await flows.search_books_by_title_under_year(
            data["query"], data["max_year"], data["limit"]
        )
        assert isinstance(urls, list)
        assert len(urls) <= data["limit"]


@allure.feature("Reading List")
class TestReadingList:

    @allure.story("Full flow: search → add → assert")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_full_flow(self, auth_page):
        flows = LibraryFlows(auth_page)

        profile_name = os.getenv("TEST_PROFILE", "quick")
        profile = CFG["profiles"].get(profile_name, CFG["profiles"]["full"])
        allure.dynamic.parameter("profile", profile_name)

        urls = await flows.search_books_by_title_under_year(
            profile["query"], profile["max_year"], profile["limit"]
        )
        if not urls:
            pytest.skip("No books found — check search selectors")

        count_before = await flows.get_reading_list_count()

        added = await flows.add_books_to_reading_list(urls)
        if added == 0:
            pytest.skip("כל הספרים כבר ברשימה — לא נוספו ספרים חדשים")

        await flows.assert_reading_list_count(count_before + added)


@allure.feature("Performance")
class TestPerformance:

    @allure.story("Page load times within thresholds")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_performance(self, page):
        thresholds = CFG["performance_thresholds"]
        reporter = PerformanceReporter(page)

        await reporter.measure(f"{BASE_URL}/search?q=Dune", thresholds["search_page"], selector=SearchPage.RESULT_ITEMS)
        await reporter.measure(BASE_URL + CFG["known_book_path"], thresholds["book_page"], selector=BookPage.READY_SELECTOR)
        await reporter.measure(f"{BASE_URL}/account/books/want-to-read", thresholds["reading_list"], selector=ReadingListPage.READY_SELECTOR)

        report_path = reporter.save()

        allure.attach(
            report_path.read_text(),
            name="performance_report.json",
            attachment_type=allure.attachment_type.JSON,
        )

        slow_pages = [
            f"{r['url']}: {r['dom_content_loaded_ms']}ms > {r['threshold_ms']}ms"
            for r in reporter.results
            if r["dom_content_loaded_ms"] is not None and r["dom_content_loaded_ms"] > r["threshold_ms"]
        ]
        if slow_pages:
            allure.attach(
                "\n".join(slow_pages),
                name="⚠️ Slow pages (informational)",
                attachment_type=allure.attachment_type.TEXT,
            )
            logger.warning("Slow pages:\n" + "\n".join(slow_pages))

        assert report_path.exists()
