import logging
from .base_page import BasePage

logger = logging.getLogger(__name__)


class BookPage(BasePage):
    PRIMARY_BTN      = "button.book-progress-btn.primary-action"
    DROPDOWN_TOGGLE  = "a.generic-dropper__dropclick"
    WANT_TO_READ_BTN = "div.read-statuses button:has-text('Want to Read')"
    ALREADY_READ_BTN = "div.read-statuses button:has-text('Already Read')"
    CURRENTLY_READING_BTN = "div.read-statuses button:has-text('Currently Reading')"

    async def _assert_authenticated(self):
        await self.page.wait_for_load_state("domcontentloaded", timeout=10000)
        url = self.page.url
        if "/account/login" in url:
            raise RuntimeError(
                "הסשן פג — האתר הפנה לדף הלוגין במהלך הטסט. "
                f"URL נוכחי: {url}\n"
                "פתרון: הרץ: python3 save_session.py כדי לחדש את session.json"
            )
        if await self.page.query_selector("#username"):
            raise RuntimeError(f"הסשן פג — טופס לוגין מוצג. URL: {url}")
        for sel in ("iframe[src*='captcha']", "div.g-recaptcha", "#cf-challenge-running", "#challenge-form"):
            if await self.page.query_selector(sel):
                raise RuntimeError(f"CAPTCHA זוהה. URL: {url}\nהמתן מספר דקות והרץ שוב.")

    async def _click_want_to_read(self) -> bool:
        """Click primary 'Want to Read' only when book is NOT in any reading list (unactivated).
        Never touches dropdown — clicking 'Want to Read' in dropdown on an already-listed book removes it."""
        btn = await self.page.query_selector(self.PRIMARY_BTN)
        if btn and await btn.is_visible():
            classes = await btn.get_attribute("class") or ""
            if "unactivated" in classes:
                await self._human_click(self.PRIMARY_BTN)
                await self.page.wait_for_load_state("load", timeout=15000)
                return True
        # Book already in some reading list state (or button not found) — skip
        logger.info(f"Book already in reading list or no primary button: {self.page.url}")
        return False

    async def _click_via_dropdown(self, selector: str) -> bool:
        """Open dropdown and click a button inside div.read-statuses."""
        toggle = await self.page.query_selector(self.DROPDOWN_TOGGLE)
        if not toggle:
            logger.warning(f"Dropdown toggle not found on {self.page.url}")
            return False
        await self._human_click(self.DROPDOWN_TOGGLE)
        try:
            await self.page.wait_for_selector(selector, state="visible", timeout=5000)
        except Exception:
            logger.warning(f"Dropdown did not expose '{selector}' on {self.page.url}")
            return False
        await self._human_click(selector)
        await self.page.wait_for_load_state("load", timeout=15000)
        return True

    async def add_to_reading_list(self) -> str:
        await self._assert_authenticated()
        if await self._click_want_to_read():
            await self._delay("action")
            logger.info(f"Clicked 'Want to Read' on {self.page.url}")
            return "Want to Read"
        logger.info(f"Book already in reading list or no button: {self.page.url}")
        return "not_added"
