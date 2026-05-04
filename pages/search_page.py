import re
from .base_page import BasePage
from config.settings import BASE_URL


class SearchPage(BasePage):
    SEARCH_INPUT = "input[name='q']"
    SEARCH_BUTTON = "button[type='submit']"
    RESULT_ITEMS = "li.searchResultItem"
    BOOK_YEAR = "span.resultDetails"
    BOOK_LINK = "a[href*='/works/']"
    NEXT_PAGE = "a[title='next page']"

    async def search(self, query: str):
        await self.page.fill(self.SEARCH_INPUT, query)
        await self.page.click(self.SEARCH_BUTTON)
        await self.page.wait_for_load_state("domcontentloaded")

    async def get_result_items(self):
        return await self.page.query_selector_all(self.RESULT_ITEMS)

    async def has_next_page(self) -> bool:
        btn = await self.page.query_selector(self.NEXT_PAGE)
        return btn is not None

    async def go_to_next_page(self):
        await self.page.click(self.NEXT_PAGE)
        await self.page.wait_for_load_state("domcontentloaded")
        await self._delay("pagination")

    @staticmethod
    def _extract_year(text: str) -> int | None:
        matches = re.findall(r'\b(1[0-9]{3}|20[012][0-9])\b', text)
        return int(matches[0]) if matches else None

    async def collect_urls_under_year(self, max_year: int, limit: int) -> list[str]:
        collected: list[str] = []

        while len(collected) < limit:
            items = await self.get_result_items()

            for item in items:
                if len(collected) >= limit:
                    break

                year_el = await item.query_selector(self.BOOK_YEAR)
                if not year_el:
                    continue

                year_text = await year_el.inner_text()
                year = self._extract_year(year_text)
                if year is None or year > max_year:
                    continue

                link_el = await item.query_selector(self.BOOK_LINK)
                if not link_el:
                    continue

                href = await link_el.get_attribute("href")
                url = BASE_URL + href
                if url not in collected:
                    collected.append(url)

            if len(collected) < limit and await self.has_next_page():
                await self.go_to_next_page()
            else:
                break

        return collected
