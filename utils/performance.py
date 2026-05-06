import time
import json
import logging
from datetime import datetime
from pathlib import Path
from playwright.async_api import Page

logger = logging.getLogger(__name__)

_JS = """() => {
    const nav = performance.getEntriesByType('navigation')[0];
    const paint = performance.getEntriesByType('paint');
    const fp = paint.find(e => e.name === 'first-paint');
    return {
        load_time_ms: nav && nav.loadEventEnd > 0 ? Math.round(nav.loadEventEnd) : null,
        dom_content_loaded_ms: nav && nav.domContentLoadedEventEnd > 0 ? Math.round(nav.domContentLoadedEventEnd) : null,
        first_paint_ms: fp ? Math.round(fp.startTime) : null
    };
}"""


class PerformanceReporter:
    """Measures time-to-element for key page selectors — unaffected by external resources."""

    def __init__(self, page: Page, report_path: str = "performance_report.json"):
        self.page = page
        self.report_path = Path(report_path)
        self._results: list[dict] = []
        self.report_path.unlink(missing_ok=True)

    async def measure(self, url: str, threshold_ms: int, selector: str) -> dict:
        last_exc: Exception | None = None
        for attempt in range(3):
            if attempt > 0:
                wait_s = 15 * attempt
                logger.warning(f"Retrying measure [{url}] in {wait_s}s (attempt {attempt + 1}/3)")
                await self.page.wait_for_timeout(wait_s * 1000)
            try:
                t_start = time.monotonic()
                await self.page.goto(url, wait_until="load")
                await self.page.wait_for_selector(selector, state="attached", timeout=30000)
                break
            except Exception as e:
                last_exc = e
        else:
            raise last_exc

        time_to_element_ms = int((time.monotonic() - t_start) * 1000)
        browser_metrics = await self.page.evaluate(_JS)

        metrics = {
            "url": url,
            "selector": selector,
            "time_to_element_ms": time_to_element_ms,
            "threshold_ms": threshold_ms,
            **browser_metrics,
            "timestamp": datetime.now().isoformat(),
        }

        load_time_ms = browser_metrics.get("load_time_ms") or time_to_element_ms
        if load_time_ms > threshold_ms:
            logger.warning(
                f"Slow page [{url}]: load_time={load_time_ms}ms > {threshold_ms}ms"
            )

        self._results.append(metrics)
        return metrics

    def save(self) -> Path:
        self.report_path.write_text(
            json.dumps(self._results, indent=2, ensure_ascii=False)
        )
        logger.info(f"Performance report saved → {self.report_path}")
        return self.report_path

    @property
    def results(self) -> list[dict]:
        return list(self._results)
