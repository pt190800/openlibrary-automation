import time
import json
import logging
from datetime import datetime
from pathlib import Path
from playwright.async_api import Page

logger = logging.getLogger(__name__)

_JS = """() => {
    const t = performance.timing;
    const paint = performance.getEntriesByType('paint');
    const fp = paint.find(e => e.name === 'first-paint');
    return {
        dom_content_loaded_ms: t.domContentLoadedEventEnd - t.navigationStart,
        first_paint_ms: fp ? Math.round(fp.startTime) : null
    };
}"""


class PerformanceReporter:
    """Measures time-to-element for key page selectors — unaffected by external resources."""

    def __init__(self, page: Page, report_path: str = "performance_report.json"):
        self.page = page
        self.report_path = Path(report_path)
        self._results: list[dict] = []

    async def measure(self, url: str, threshold_ms: int, selector: str) -> dict:
        t_start = time.monotonic()
        await self.page.goto(url, wait_until="commit")
        await self.page.wait_for_selector(selector, state="attached", timeout=30000)
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

        if time_to_element_ms > threshold_ms:
            logger.warning(
                f"Slow page [{url}]: time_to_element={time_to_element_ms}ms > {threshold_ms}ms"
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
