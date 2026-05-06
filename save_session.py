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
        # מנסה להשתמש ב-Chrome האמיתי תחילה — פחות סיכוי לחסימה
        try:
            browser = await p.chromium.launch(
                headless=False,
                channel="chrome",
                args=["--disable-blink-features=AutomationControlled"],
            )
            print("✓ Chrome האמיתי הופעל")
        except Exception:
            browser = await p.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )
            print("✓ Playwright Chromium הופעל (Chrome לא נמצא)")

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
        await page.goto(BASE_URL, wait_until="domcontentloaded")

        print()
        print("  ╔══════════════════════════════════════════════════════════════╗")
        print("  ║  דפדפן נפתח על דף הבית של OpenLibrary                      ║")
        print("  ║                                                              ║")
        print("  ║  1. לחץ על 'Log In' בתפריט העליון                          ║")
        print("  ║  2. הזן אימייל + סיסמה ולחץ Log In                         ║")
        print("  ║  3. אם יש CAPTCHA — פתור אותה                               ║")
        print("  ║  4. המתן עד שתראה את דף הבית / הפרופיל שלך                ║")
        print("  ║                                                              ║")
        print("  ║  הסשן יישמר אוטומטית ברגע שתהיה מחובר.                     ║")
        print("  ╚══════════════════════════════════════════════════════════════╝")
        print()

        print("ממתין שתלחץ Log In... (עד 10 דקות)")
        try:
            await page.wait_for_url(
                lambda url: "/account/login" in url or "/verify_human" in url,
                timeout=600_000,
            )
        except Exception:
            print("❌  timeout — לא זוהה ניווט לדף הלוגין. הרץ שוב.")
            await browser.close()
            return

        print("ממתין להתחברות...")
        try:
            await page.wait_for_url(
                lambda url: "/account/login" not in url and "/verify_human" not in url,
                timeout=600_000,
            )
        except Exception:
            print("❌  timeout — לא זוהה לוגין תוך 10 דקות. הרץ שוב.")
            await browser.close()
            return

        await ctx.storage_state(path=SESSION_FILE)
        print(f"✅  session.json נשמר בהצלחה!")
        print(f"   URL נוכחי: {page.url}")
        await browser.close()


asyncio.run(main())
