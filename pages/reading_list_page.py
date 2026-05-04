from .base_page import BasePage

BASE_URL = "https://openlibrary.org"


class ReadingListPage(BasePage):
    BOOK_ITEMS = "li.searchResultItem"

    async def open(self):
        await self.navigate(f"{BASE_URL}/account/books/want-to-read")

    async def get_book_count(self) -> int:
        try:
            await self.page.wait_for_selector(self.BOOK_ITEMS, timeout=5000)
        except Exception:
            return 0
        items = await self.page.query_selector_all(self.BOOK_ITEMS)
        return len(items)
