import os
import re
import time
import shutil
import asyncio
import random
import pytest
import pytest_asyncio
import allure
from pathlib import Path
from playwright.async_api import async_playwright
from dotenv import load_dotenv

from config.settings import BASE_URL
from pages.base_page import _MAX_RETRIES as _LOGIN_MAX_RETRIES

load_dotenv()
SCREENSHOTS_DIR = Path("screenshots")
TRACES_DIR = Path("reports/traces")
SCREENSHOTS_DIR.mkdir(exist_ok=True)
TRACES_DIR.mkdir(parents=True, exist_ok=True)


def pytest_sessionstart(session):
    """מנקה screenshots וtraces מריצות קודמות לפני תחילת הסשן."""
    for directory in (SCREENSHOTS_DIR, TRACES_DIR):
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True, exist_ok=True)

STEALTH_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
STEALTH_INIT_SCRIPT = """
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
    Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
    window.chrome = { runtime: {} };
"""
STEALTH_LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--window-size=1920,1080",
    "--disable-gpu",
]
STEALTH_VIEWPORT = {"width": 1920, "height": 1080}

_LOGIN_PAGE_TIMEOUT_MS = 20_000


async def _new_stealth_context(p, storage_state=None):
    browser = await p.chromium.launch(headless=True, args=STEALTH_LAUNCH_ARGS)
    kwargs = {"user_agent": STEALTH_UA, "viewport": STEALTH_VIEWPORT}
    if storage_state:
        kwargs["storage_state"] = storage_state
    ctx = await browser.new_context(**kwargs)
    await ctx.add_init_script(STEALTH_INIT_SCRIPT)
    return browser, ctx


# ── full failure reflection ──────────────────────────────────────────────────

async def _capture_failure(page, node_id: str, console_errors: list[str]):
    """מצלם screenshot, שולף URL + title + שגיאות console ומדפיס הכל."""
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", node_id)[:120]
    sep = "=" * 60

    # ── screenshot ──
    shot_path = SCREENSHOTS_DIR / f"FAIL_{safe}.png"
    try:
        await page.screenshot(path=str(shot_path), full_page=True)
        allure.attach.file(
            str(shot_path),
            name="Screenshot — כישלון",
            attachment_type=allure.attachment_type.PNG,
        )
    except Exception as e:
        shot_path = None
        print(f"⚠️  screenshot failed: {e}")

    # ── page info ──
    try:
        current_url   = page.url
        current_title = await page.title()
    except Exception:
        current_url   = "N/A"
        current_title = "N/A"

    # ── HTML snapshot ──
    try:
        html = await page.content()
        allure.attach(
            html,
            name="HTML snapshot",
            attachment_type=allure.attachment_type.HTML,
        )
    except Exception:
        pass

    # ── הדפסה לטרמינל ──
    print(f"\n{sep}")
    print(f"❌  FAILED: {node_id}")
    print(f"   URL   : {current_url}")
    print(f"   Title : {current_title}")
    if shot_path:
        print(f"   Screenshot → {shot_path}")
    if console_errors:
        print("   Console errors:")
        for err in console_errors:
            print(f"     {err}")
    print(sep)

    # ── attach URL + title + console ל-Allure ──
    allure.attach(
        f"URL: {current_url}\nTitle: {current_title}",
        name="Page info בזמן הכישלון",
        attachment_type=allure.attachment_type.TEXT,
    )
    if console_errors:
        allure.attach(
            "\n".join(console_errors),
            name="Console errors",
            attachment_type=allure.attachment_type.TEXT,
        )


def pytest_runtest_setup(item):
    """השהייה לפני כל טסט כדי לא להציף את השרת בבקשות — לא רץ ב-TestPerformance."""
    if "TestPerformance" not in item.nodeid:
        time.sleep(random.uniform(8, 14))


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """שומר את תוצאת כל שלב על ה-item — ה-fixtures קוראים את rep_call ב-teardown."""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)


async def _fixture_teardown(pg, ctx, browser, request, console_errors: list[str]):
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", request.node.nodeid)[:100]
    trace_path = str(TRACES_DIR / f"{safe}.zip")
    rep = getattr(request.node, "rep_call", None)
    if rep and rep.failed:
        await _capture_failure(pg, request.node.nodeid, console_errors)
    try:
        await ctx.tracing.stop(path=trace_path)
    finally:
        await browser.close()


# ── fixtures ─────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def page(request):
    async with async_playwright() as p:
        browser, ctx = await _new_stealth_context(p)
        await ctx.tracing.start(screenshots=True, snapshots=True, sources=True)
        pg = await ctx.new_page()

        console_errors: list[str] = []
        pg.on("console", lambda msg: console_errors.append(f"[{msg.type}] {msg.text}")
              if msg.type in ("error", "warning") else None)

        yield pg

        await _fixture_teardown(pg, ctx, browser, request, console_errors)


@pytest_asyncio.fixture
async def auth_page(request):
    """Authenticated page — uses saved session (session.json) if available, else logs in fresh."""
    session_file = Path("session.json")
    username = os.getenv("OL_USERNAME")
    password = os.getenv("OL_PASSWORD")

    async with async_playwright() as p:
        if session_file.exists():
            browser, ctx = await _new_stealth_context(p, storage_state=str(session_file))
            await ctx.tracing.start(screenshots=True, snapshots=True, sources=True)
            pg = await ctx.new_page()
            await pg.goto(f"{BASE_URL}/account", wait_until="domcontentloaded")
            await pg.wait_for_timeout(1500)
            if "/account/login" in pg.url:
                await pg.screenshot(path=str(SCREENSHOTS_DIR / "session_expired.png"))
                await ctx.tracing.stop(path=str(TRACES_DIR / "session_expired.zip"))
                await browser.close()
                raise RuntimeError(
                    "session.json פג תוקף — האתר הפנה ל-/account/login.\n"
                    "הרץ: python3 save_session.py כדי לחדש את הסשן."
                )
            print("\n✅  session.json תקין — הסשן פעיל")
        else:
            browser, ctx = await _new_stealth_context(p)
            await ctx.tracing.start(screenshots=True, snapshots=True, sources=True)
            pg = await ctx.new_page()

        if not session_file.exists():
            if not username or not password:
                print("\n⚠️  OL_USERNAME / OL_PASSWORD חסרים ב-.env — טסטי auth ידולגו")
            else:
                login_url = f"{BASE_URL}/account/login"
                resp = None
                for attempt in range(_LOGIN_MAX_RETRIES):
                    resp = await pg.goto(login_url, wait_until="networkidle")
                    if resp is None or resp.status != 429:
                        break
                    wait_s = 5 * (2 ** attempt) + random.uniform(-2, 2)
                    print(f"\n⏳ HTTP 429 על login — ממתין {wait_s:.1f}s (ניסיון {attempt + 1}/{_LOGIN_MAX_RETRIES})")
                    await asyncio.sleep(max(wait_s, 1))
                else:
                    raise RuntimeError(
                        f"HTTP 429 — האתר חסם בקשות לאחר {_LOGIN_MAX_RETRIES} ניסיונות. המתן כמה דקות והרץ שוב."
                    )
                if resp and resp.status == 429:
                    raise RuntimeError(
                        "HTTP 429 — האתר חסם בקשות זמנית (rate limit). המתן 2-3 דקות והרץ שוב."
                    )
                try:
                    await pg.wait_for_selector("#username", state="visible", timeout=_LOGIN_PAGE_TIMEOUT_MS)
                except Exception:
                    await pg.screenshot(path=str(SCREENSHOTS_DIR / "login_failed.png"))
                    raise RuntimeError(
                        f"עמוד הלוגין לא נטען כראוי (URL: {pg.url}). "
                        "צילום מסך נשמר ב-screenshots/login_failed.png"
                    )
                await pg.fill("#username", username)
                await pg.fill("#password", password)
                await pg.click("button[type='submit'], input[type='submit']")
                await pg.wait_for_load_state("networkidle")
                await pg.wait_for_timeout(random.randint(2000, 3000))

                # טיפול בדף verify_human — נסה ללחוץ אוטומטית על הצ'קבוקס
                if "/verify_human" in pg.url:
                    print("\n   נפתח דף verify_human — מנסה לאשר אוטומטית...")
                    await pg.wait_for_load_state("domcontentloaded")
                    await pg.wait_for_timeout(1500)

                    verify_selectors = [
                        "text=Verify you are human",
                        "a:has-text('Verify you are human')",
                        "button:has-text('Verify you are human')",
                        "input[value*='Verify']",
                        "a[href*='verify']",
                    ]
                    clicked = False
                    for sel in verify_selectors:
                        try:
                            el = await pg.wait_for_selector(sel, timeout=3000)
                            if el:
                                await el.click()
                                print(f"   ✅ לחצתי על '{sel}'")
                                clicked = True
                                await pg.wait_for_timeout(1000)
                                break
                        except Exception:
                            pass

                    if not clicked:
                        await pg.screenshot(path=str(SCREENSHOTS_DIR / "verify_human.png"))
                        raise RuntimeError(
                            "דף verify_human נפתח אך לא נמצא כפתור 'Verify you are human'.\n"
                            "הרץ: python3 save_session.py כדי להתחבר ידנית ולשמור סשן."
                        )

                    try:
                        await pg.wait_for_url(
                            lambda url: "/verify_human" not in url,
                            timeout=30000
                        )
                    except Exception:
                        await pg.screenshot(path=str(SCREENSHOTS_DIR / "verify_human_timeout.png"))
                        raise RuntimeError(
                            "verify_human לא נפתר תוך 30 שניות.\n"
                            "הרץ: python3 save_session.py כדי להתחבר ידנית."
                        )
                    await pg.wait_for_load_state("networkidle")

        console_errors: list[str] = []
        pg.on("console", lambda msg: console_errors.append(f"[{msg.type}] {msg.text}")
              if msg.type in ("error", "warning") else None)

        yield pg

        await _fixture_teardown(pg, ctx, browser, request, console_errors)
