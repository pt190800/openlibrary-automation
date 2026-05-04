"""
הרץ פעם אחת לפני הטסטים:
    python3 save_session.py

פותח דפדפן — התחבר ידנית — הסשן נשמר אוטומטית ל-session.json.
"""
import asyncio
from playwright.async_api import async_playwright

SESSION_FILE = "session.json"
BASE_URL = "https://openlibrary.org"


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        await ctx.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins',   { get: () => [1, 2, 3] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            window.chrome = { runtime: {} };
        """)
        page = await ctx.new_page()
        await page.goto(f"{BASE_URL}/account/login", wait_until="domcontentloaded")

        print()
        print("  ╔══════════════════════════════════════════════════════════════╗")
        print("  ║  דפדפן נפתח — התחבר ידנית:                                 ║")
        print("  ║  1. אם יש 'Verify you are human' — לחץ עליו                ║")
        print("  ║  2. הזן אימייל + סיסמה ולחץ Log In                         ║")
        print("  ║  3. אם יש CAPTCHA נוסף — פתור אותה                         ║")
        print("  ║  4. המתן עד שתראה את דף הבית / הפרופיל שלך                ║")
        print("  ║                                                              ║")
        print("  ║  הסשן יישמר אוטומטית ברגע שתהיה מחובר.                     ║")
        print("  ╚══════════════════════════════════════════════════════════════╝")
        print()

        # ממתין עד שהמשתמש מחובר — כלומר הגיע לדף שאינו login
        print("ממתין לאימות... (עד 10 דקות)")
        try:
            await page.wait_for_url(
                lambda url: "/account/login" not in url and "/verify_human" not in url,
                timeout=600_000,  # 10 דקות
            )
        except Exception:
            print("❌  timeout — לא זוהה לוגין תוך 10 דקות. הרץ שוב.")
            await browser.close()
            return

        # וידוא שהסשן תקין — ניווט לדף המוגן
        await page.goto(
            f"{BASE_URL}/account/books/want-to-read",
            wait_until="domcontentloaded",
        )
        if "/account/login" in page.url or "/verify_human" in page.url:
            print(f"❌  עדיין לא מחובר (URL: {page.url}). נסה שוב.")
            await browser.close()
            return

        # שמירת session
        await ctx.storage_state(path=SESSION_FILE)
        print(f"✅  session.json נשמר בהצלחה!")
        print(f"   URL נוכחי: {page.url}")
        await browser.close()


asyncio.run(main())
