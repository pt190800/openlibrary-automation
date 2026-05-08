from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from .base_page import BasePage
from config.settings import BASE_URL


_MAX_PAGES = 50
_ITEMS_TIMEOUT_MS = 15_000


class ReadingListPage(BasePage):
    BOOK_ITEMS = "ul.list-books li.searchResultItem"
    READY_SELECTOR = "h1"
    NEXT_PAGE = "a[title='next page'], a[aria-label='Next Page']"

    async def open(self):
        await self.navigate(f"{BASE_URL}/account/books/want-to-read")

    async def get_book_count(self) -> int:
        total = 0
        for _ in range(_MAX_PAGES):
            try:
                await self.page.wait_for_selector(self.BOOK_ITEMS, timeout=_ITEMS_TIMEOUT_MS)
            except PlaywrightTimeoutError:
                break  # אין ספרים בדף — סוף הרשימה
            items = await self.page.query_selector_all(self.BOOK_ITEMS)
            total += len(items)
            btn = await self.page.query_selector(self.NEXT_PAGE)
            if not btn:
                break
            await self.page.click(self.NEXT_PAGE)
            await self.page.wait_for_load_state("domcontentloaded")
        return total
