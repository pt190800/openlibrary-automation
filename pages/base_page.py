import re
import random
import asyncio
import logging
from pathlib import Path
from playwright.async_api import Page

SCREENSHOTS_DIR = Path("screenshots")
SCREENSHOTS_DIR.mkdir(exist_ok=True)

logger = logging.getLogger(__name__)

DELAYS = {
    "navigate":   (800,  1800),
    "pagination": (1500, 2500),
    "action":     (1000, 2000),
    "login":      (2000, 3000),
}

_MAX_RETRIES = 4
_BACKOFF_BASE = 5      # seconds — doubles each attempt: 5, 10, 20, 40
_BACKOFF_JITTER = 2    # ±2s random jitter so parallel tests don't collide


class BasePage:
    def __init__(self, page: Page):
        self.page = page

    async def _delay(self, kind: str = "navigate"):
        lo, hi = DELAYS.get(kind, (500, 1000))
        ms = random.randint(lo, hi)
        logger.debug(f"delay [{kind}] {ms}ms")
        await self.page.wait_for_timeout(ms)

    async def _human_mouse_move(self, steps: int = 4):
        """Random mouse path through intermediate points — mimics human hand movement."""
        vp = self.page.viewport_size or {"width": 1280, "height": 720}
        w, h = vp["width"], vp["height"]
        for _ in range(steps):
            x = random.randint(80, w - 80)
            y = random.randint(80, h - 80)
            # move in two micro-steps with slight overshoot to look organic
            mid_x = x + random.randint(-30, 30)
            mid_y = y + random.randint(-30, 30)
            await self.page.mouse.move(mid_x, mid_y)
            await self.page.wait_for_timeout(random.randint(40, 120))
            await self.page.mouse.move(x, y)
            await self.page.wait_for_timeout(random.randint(30, 90))

    async def _human_click(self, selector: str):
        """Move mouse to element with slight overshoot, then click."""
        el = await self.page.wait_for_selector(selector, state="visible", timeout=8000)
        box = await el.bounding_box()
        if not box:
            await self.page.click(selector)
            return
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2
        # approach from a random offset
        await self.page.mouse.move(cx + random.randint(-60, 60), cy + random.randint(-40, 40))
        await self.page.wait_for_timeout(random.randint(80, 180))
        await self.page.mouse.move(cx, cy)
        await self.page.wait_for_timeout(random.randint(40, 100))
        await self.page.mouse.click(cx, cy)

    async def navigate(self, url: str):
        """Navigate with exponential backoff on HTTP 429 (rate limit)."""
        for attempt in range(_MAX_RETRIES):
            resp = await self.page.goto(url, wait_until="domcontentloaded")
            if resp is None or resp.status != 429:
                await self._human_mouse_move(steps=random.randint(2, 4))
                await self._delay("navigate")
                return
            wait_s = _BACKOFF_BASE * (2 ** attempt) + random.uniform(-_BACKOFF_JITTER, _BACKOFF_JITTER)
            wait_s = max(wait_s, 1)
            logger.warning(f"HTTP 429 on {url} — waiting {wait_s:.1f}s (attempt {attempt + 1}/{_MAX_RETRIES})")
            await asyncio.sleep(wait_s)

        raise RuntimeError(
            f"HTTP 429 — האתר חסם בקשות לאחר {_MAX_RETRIES} ניסיונות על {url}. "
            "המתן כמה דקות והרץ שוב."
        )

    async def take_screenshot(self, name: str) -> str | None:
        safe = re.sub(r"[^a-zA-Z0-9_-]", "_", name)[:120]
        path = SCREENSHOTS_DIR / f"{safe}.png"
        try:
            await self.page.screenshot(path=str(path), timeout=10000)
            return str(path)
        except Exception as e:
            logger.warning(f"Screenshot failed [{name}]: {e}")
            return None
