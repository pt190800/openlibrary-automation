import logging
import allure
from urllib.parse import quote_plus
from playwright.async_api import Page

from config.settings import BASE_URL
from pages.search_page import SearchPage
from pages.book_page import BookPage
from pages.reading_list_page import ReadingListPage

logger = logging.getLogger(__name__)


class LibraryFlows:
    """Encapsulates the three core E2E flows used across test classes."""

    def __init__(self, page: Page):
        self.page = page

    @allure.step("Search '{query}' — max year {max_year}, limit {limit}")
    async def search_books_by_title_under_year(
        self, query: str, max_year: int, limit: int = 5
    ) -> list[str]:
        search = SearchPage(self.page)
        await search.navigate(f"{BASE_URL}/search?q={quote_plus(query)}")
        return await search.collect_urls_under_year(max_year, limit)

    async def _assert_session(self) -> None:
        await self.page.goto(
            f"{BASE_URL}/account/books/want-to-read", wait_until="domcontentloaded"
        )
        if "/account/login" in self.page.url:
            raise RuntimeError(
                "הסשן אינו תקין — האתר הפנה לדף הלוגין.\n"
                "הרץ: python3 save_session.py כדי לחדש את session.json"
            )

    @allure.step("Add books to reading list")
    async def add_books_to_reading_list(self, urls: list[str]) -> int:
        book = BookPage(self.page)
        added = 0
        for i, url in enumerate(urls):
            with allure.step(f"Book {i + 1}/{len(urls)}: {url}"):
                await book.navigate(url)
                action = await book.add_to_reading_list()
                if action != "not_added":
                    added += 1
                screenshot = await book.take_screenshot(url)
                logger.info(f"[{action}] {url} → {screenshot}")
                if screenshot:
                    allure.attach.file(
                        screenshot, name=url, attachment_type=allure.attachment_type.PNG
                    )
        return added

    async def _get_shelf_count(self, rl: ReadingListPage, shelf: str) -> int:
        if shelf == "already-read":
            await rl.open_already_read()
        else:
            await rl.open()
        return await rl.get_book_count()

    @allure.step("Get reading list count")
    async def get_reading_list_count(self) -> int:
        await self._assert_session()
        rl = ReadingListPage(self.page)
        want = await self._get_shelf_count(rl, "want-to-read")
        already = await self._get_shelf_count(rl, "already-read")
        return want + already

    @allure.step("Assert reading list count = {expected_count}")
    async def assert_reading_list_count(self, expected_count: int) -> None:
        rl = ReadingListPage(self.page)
        want = await self._get_shelf_count(rl, "want-to-read")
        already = await self._get_shelf_count(rl, "already-read")
        actual = want + already
        screenshot = await rl.take_screenshot("reading_list_assert")
        if screenshot:
            allure.attach.file(
                screenshot, name="reading_list", attachment_type=allure.attachment_type.PNG
            )
        assert actual == expected_count, f"Expected {expected_count} books, got {actual}"
