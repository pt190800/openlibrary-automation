from .base_page import BasePage
from config.settings import BASE_URL


class ReadingListPage(BasePage):
    BOOK_ITEMS = "li.searchResultItem"
    READY_SELECTOR = "h1"
    NEXT_PAGE = "a[title='next page']"

    async def open(self):
        await self.navigate(f"{BASE_URL}/account/books/want-to-read")

    async def get_book_count(self) -> int:
        total = 0
        while True:
            try:
                await self.page.wait_for_selector(self.BOOK_ITEMS, timeout=5000)
            except Exception:
                break
            items = await self.page.query_selector_all(self.BOOK_ITEMS)
            total += len(items)
            btn = await self.page.query_selector(self.NEXT_PAGE)
            if not btn:
                break
            await self.page.click(self.NEXT_PAGE)
            await self.page.wait_for_load_state("domcontentloaded")
        return total
