#ניתוח באגים בקובץ מטלה 3 באגים הסבר ופתרון:
בעיה 1:
בפונקציה שמוציאה שנה יש טקסט באתר עצמו שהוא First published in 1933
וצריך לחלץ רק את המספר שם משתמשים ב strip()
אבל צריך לציין בסוגריים בתוכו את מה אנחנו לא צריכים שזה הטקסט חוץ ממספר... ולכן אפשר להוסיף בתוך הסוגריים כדי שיהיה אפשר לחלץ רק מספר!
או לחלץ עם ריגקס(re) שזה עוד אופציה

בעיה 2.
בפונקציה search_books_by_title_under_year יש הגבלה על הלימיט אבל רק בוויל ולא בפור מה שגורם שבפועל בלולאת פור אייטמס הוא אוסף את כל התוצאות מה-search והlimit לא עוזר בכלל
הפתרון
להוסיף תנאי בתוך לולאת הfor :
if len(collected = limit):
    break
(עדיף מאשר תנאי הפוך כי בבריק הוא לא עובר על הכל ובוחר מה לשי ומה לא אלא ברגע שמגיע ללימיט יוצא מהלולאה)

בעיה 3.
(סלקטור)
בפונקציה add_books_to_reading_list יש לחיצה על כפתור .want-to-read-btn
שזה לא טוב אין כזה קלאס בDOM 
פתרון.
קודם כל עדיף ויותר יציב לעשות text=Want to Read
כי מתעלמים מהקלאס ובודקים לפי טקסט
דבר שני לאחר בדיקה הקלאס הנכון הוא 
"button.book-progress-btn.primary-action:has-text('Want to Read')"
כאן אנחנו גם מגיעים לכפתור עצמו וגם בודקים את הטקסט ליתר ביטחון


# ReadMeAIBugs — באגים שהתגלו בריצה אמיתית ובבדיקת DevTools

## באג 1 — Event Loop Mismatch בין fixtures (נמצא בריצה אמיתית)

**קוד בעייתי:**
```python
@pytest_asyncio.fixture(scope="session")
async def browser():
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        yield b
        await b.close()

@pytest_asyncio.fixture          # scope="function" (ברירת מחדל)
async def page(browser):
    p = await browser.new_page()  # ← קריסה כאן
    yield p
    await p.close()
```

**הסבר:** ב-pytest-asyncio עם `asyncio_mode=auto`, כל טסט מקבל event loop חדש משלו. ה-fixture `browser` נוצר ב-event loop של הטסט הראשון. כשהטסט השני מתחיל, הוא מקבל event loop חדש — ואז `browser.new_page()` נכשל כי ה-browser שייך ל-loop אחר.

**שגיאה:**
```
ValueError: Browser.new_page: The future belongs to a different loop
than the one specified as the loop argument
```

**תיקון:** הסרת הסקופ המשותף — כל fixture מנהל browser עצמאי בתוך `async with async_playwright()`:
```python
@pytest_asyncio.fixture
async def page():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        pg = await browser.new_page()
        yield pg
        await browser.close()   # browser נסגר בסיום כל טסט — ניקוי מלא
```

**מדוע זה עובד:** כל הפעולות (פתיחת browser, יצירת page, סגירה) קורות באותו event loop של הטסט. אין שיתוף מצב בין טסטים.

---

## באג 2 — סלקטור `span.bookEditions` לא קיים יותר (נמצא בריצה אמיתית)

**קוד בעייתי:**
```python
BOOK_YEAR = "span.bookEditions"
```

**הסבר:** האתר OpenLibrary עדכן את מבנה ה-HTML. האלמנט `span.bookEditions` הוסר לחלוטין. כתוצאה מכך `query_selector` החזיר `None` לכל תוצאה, הלולאה דילגה על הכל, והפונקציה החזירה רשימה ריקה תמיד — בלי שגיאה, בלי התראה.

**שגיאה:** לא קריסה — הטסט פשוט דילג על הכל:
```
tests/test_openlibrary.py::TestReadingList::test_full_flow SKIPPED
"No books found — check search selectors"
```

**תיקון:** עדכון לסלקטור הנוכחי באתר:
```python
BOOK_YEAR = "span.resultDetails span"
# מכיל: "First published in 1965" — הregex מחלץ את השנה
```

---

## באג 3 — סלקטורים `.want-to-read` / `.already-read` לא קיימים יותר (נמצא בריצה אמיתית)

**קוד בעייתי:**
```python
WANT_TO_READ_BTN   = ".want-to-read"
ALREADY_READ_BTN   = ".already-read"
```

**הסבר:** האתר שינה את מבנה כפתורי הרשימה. ה-classes `.want-to-read` ו-`.already-read` הוחלפו בכפתורים גנריים מסוג `button.nostyle-btn` עם טקסט פנימי. התוצאה: `query_selector` החזיר `None`, הפונקציה החזירה `"not_added"` לכל ספר, ולא נוסף שום דבר לרשימה.

**תיקון:** שימוש בסלקטור `:has-text()` של Playwright:
```python
WANT_TO_READ_BTN   = "button.nostyle-btn:has-text('Want to Read')"
ALREADY_READ_BTN   = "button.nostyle-btn:has-text('Already Read')"
```

---

## באג 4 — `max_year=1800` לא מחזיר רשימה ריקה (נמצא בריצה אמיתית)

**קוד בעייתי:**
```python
async def test_search_no_results(self, page):
    urls = await search_books_by_title_under_year(page, "Dune", 1800, 5)
    assert urls == []
```

**הסבר:** הטסט הניח ששנת 1800 מוקדמת מדי לכל ספר בנושא "Dune". אך OpenLibrary מחזיר ספרים עתיקים שמכילים את המילה "dune" (חול/נוף) בכותרת או תיאור — כמו "Fables" (1484) ועוד. כתוצאה מכך הטסט נכשל כי קיבל 5 URLs במקום 0.

**שגיאה:**
```
AssertionError: assert ['https://openlibrary.org/works/OL50348W/Fables?...'] == []
Left contains 5 more items
```

**תיקון:** שימוש בשנה שקדמה להמצאת הדפוס — מבטיח 0 תוצאות:
```python
urls = await search_books_by_title_under_year(page, "Dune", 1300, 5)
assert urls == []
```

---

## באג 5 — לחיצה על כפתור עם class `hidden` (נמצא בריצה אמיתית)

**קוד בעייתי:**
```python
WANT_TO_READ_BTN = "button.nostyle-btn:has-text('Want to Read')"
...
btn = await self.page.query_selector(selector)
if btn:
    await btn.click()
```

**הסבר:** בעמוד הספר, כפתור "Want to Read" מגיע עם class `hidden` בטעינה הראשונית — הוא מוסתר מהמשתמש בתוך תפריט נפתח:
```html
<button class="nostyle-btn hidden">Want to Read</button>   ← מוסתר
<button class="nostyle-btn ">Currently Reading</button>    ← נראה
<button class="nostyle-btn ">Already Read</button>         ← נראה
```

`query_selector` מוצא אותו (כי הוא קיים ב-DOM), אבל Playwright ב-`click()` רגיל יזרוק שגיאה כי האלמנט לא visible — או יחליק בשקט אם האלמנט מחוץ לתצוגה.

**שגיאה אפשרית:**
```
TimeoutError: element is not visible
```
או — גרוע יותר — לחיצה שלא מבצעת כלום בלי שגיאה.

**תיקון:** שימוש ב-`force=True` לאילוץ לחיצה ללא תנאי visibility, **או** לחיצה קודם על כפתור ה-dropdown כדי לחשוף את האפשרויות:
```python
# אפשרות 1 — force click (פשוט, אבל פחות "אנושי")
await btn.click(force=True)

# אפשרות 2 — פתח dropdown קודם (מומלץ)
PRIMARY_BTN = "button.book-progress-btn.primary-action"
await self.page.click(self.PRIMARY_BTN)   # פותח את התפריט
await self.page.wait_for_selector(
    "button.nostyle-btn:has-text('Want to Read')",
    state="visible"
)
await self.page.click("button.nostyle-btn:has-text('Want to Read')")
```

---

## באג 6 — סשן פג בלי שגיאה ברורה (נמצא בריצה אמיתית)

**קוד בעייתי:**
```python
btn = await self.page.query_selector(selector)
if btn:
    await btn.click()
```

**הסבר:** כשהסשן פג באמצע הטסט, OpenLibrary מפנה את הדפדפן לעמוד הלוגין (`/account/login`). הקוד ממשיך לנסות למצוא את כפתור "Want to Read" בעמוד הלוגין — הכפתור לא קיים, `query_selector` מחזיר `None`, והטסט נכשל עם `TimeoutError` או `AssertionError` לא ברורים שלא מצביעים על הבעיה האמיתית.

**שגיאה אפשרית:**
```
TimeoutError: Page.click: Timeout 30000ms exceeded.
waiting for locator("button.nostyle-btn:has-text('Want to Read')")
```
או:
```
AssertionError: Expected 1 books, got 0
```
שתיהן לא מסבירות שהסשן פג.

**תיקון:** בדיקת אימות לפני כל פעולה הדורשת login:
```python
async def _assert_authenticated(self):
    url = self.page.url
    if "/account/login" in url:
        raise RuntimeError(
            "הסשן פג — האתר הפנה לדף הלוגין במהלך הטסט. "
            f"URL נוכחי: {url}"
        )
    login_form = await self.page.query_selector("#username")
    if login_form:
        raise RuntimeError(
            "הסשן פג — טופס לוגין מוצג בעמוד הספר. "
            f"URL נוכחי: {url}"
        )

async def add_to_reading_list(self) -> str:
    await self._assert_authenticated()   # ← לפני כל פעולה
    ...
```

---

## באג 7 — סלקטור `li.listbook-item` לא קיים (נמצא בבדיקת DevTools)

**קוד בעייתי:**
```python
BOOK_ITEMS = "li.listbook-item"
```

**הסבר:** דף הרשימה (`/account/books/want-to-read`) משתמש באותה מבנה HTML כמו דף החיפוש. פריט ספר ברשימה הוא `li.searchResultItem` — לא `li.listbook-item`. הסלקטור הישן לא מצא אף אלמנט, `get_book_count()` החזיר תמיד 0, והאסרציה נכשלה.

**שגיאה:**
```
AssertionError: Expected 3 books, got 0
```

**תיקון:**
```python
BOOK_ITEMS = "li.searchResultItem"
```

---

## באג 8 — query לחיפוש לא מקודד ב-URL (נמצא בניתוח קוד)

**קוד בעייתי:**
```python
await search.navigate(f"{BASE_URL}/search?q={query}")
```

**הסבר:** כשה-query מכיל רווחים או תווים מיוחדים (למשל `"Lord of the Rings"`), הם נכנסים כמות שהם ל-URL. דפדפן יכול להמיר רווח ל-`%20` אוטומטית, אבל תווים כמו `&`, `+`, `#` ישברו את ה-URL לחלוטין. בפועל הטסט הפרמטריזאטי `test_parametrized_search[data1]` רץ עם query `"Lord of the Rings"` — שבירה אפשרית.

**שגיאה אפשרית:**
```
# URL שנוצר:
https://openlibrary.org/search?q=Lord of the Rings
# במקום:
https://openlibrary.org/search?q=Lord+of+the+Rings
```

**תיקון:**
```python
from urllib.parse import quote_plus
await search.navigate(f"{BASE_URL}/search?q={quote_plus(query)}")
```

---

## באג 9 — קריאה כפולה ל-`_assert_session()` מגדילה rate limiting (נמצא בריצה אמיתית)

**קוד בעייתי:**
```python
async def get_reading_list_count(self) -> int:
    await self._assert_session()      # ← טוען /account/books/want-to-read
    rl = ReadingListPage(self.page)
    return await rl.get_book_count()

async def add_books_to_reading_list(self, urls: list[str]) -> int:
    await self._assert_session()      # ← טוען שוב — מיותר לחלוטין
    ...
```

**הסבר:** בטסט `test_full_flow`, `get_reading_list_count` תמיד מוקרא לפני `add_books_to_reading_list`. כלומר הסשן כבר אומת ועמוד הרשימה כבר נטען. הקריאה השנייה ל-`_assert_session` טענה את העמוד שוב — בזבוז שגרם לחריגת HTTP 429 מהירה יותר מהאתר. בריצה אמיתית זה גרם לכישלון ב-Dune Messiah (הספר השני) עם:

```json
{"status": 429, "message": "Too Many Requests."}
```

**תיקון:** הסרת `_assert_session()` מ-`add_books_to_reading_list` — הבדיקה ב-`BookPage._assert_authenticated()` מספיקה:
```python
async def add_books_to_reading_list(self, urls: list[str]) -> int:
    book = BookPage(self.page)
    # אין _assert_session — הסשן אומת כבר ב-get_reading_list_count
    want_to_read_count = 0
    ...
```

---

## באג 10 — console listener נרשם אחרי הכישלון (נמצא בניתוח קוד)

**קוד בעייתי:**
```python
async def _capture_failure(page, node_id: str):
    console_errors: list[str] = []
    page.on("console", lambda msg: ...)  # ← נרשם אחרי שהטסט כבר נכשל
```

**הסבר:** `_capture_failure` נקראה מה-hook `pytest_runtest_makereport` לאחר כישלון. בשלב זה כל ה-console events (JS errors, network warnings) שהתרחשו במהלך הטסט כבר עברו — הlistener החדש לא קולט כלום. בנוסף, `loop.create_task()` יצר את ה-coroutine ללא `await`, כך שהdפדפן עלול להיסגר לפני שה-screenshot נלקח.

**שגיאה:** ה-"Console errors" בAllure תמיד ריק, גם כשהיו שגיאות JS בדף.

**תיקון:** רישום ה-listener בfixture לפני `yield`, והעברתו ל-`_capture_failure` כפרמטר:

```python
@pytest_asyncio.fixture
async def page(request):
    ...
    console_errors: list[str] = []
    pg.on("console", lambda msg: console_errors.append(...)
          if msg.type in ("error", "warning") else None)
    yield pg
    rep = getattr(request.node, "rep_call", None)
    if rep and rep.failed:
        await _capture_failure(pg, request.node.nodeid, console_errors)
    try:
        await ctx.tracing.stop(path=trace_path)
    finally:
        await browser.close()
```

---

## באג 11 — `except Exception: break` בולע שגיאות רשת בספירת ספרים (נמצא בניתוח קוד)

**קוד בעייתי:**
```python
async def get_book_count(self) -> int:
    for _ in range(_MAX_PAGES):
        try:
            await self.page.wait_for_selector(self.BOOK_ITEMS, timeout=15000)
        except Exception:
            break  # ← עוצר גם על 429, network error, crash
```

**הסבר:** `except Exception` תופס הכל — כולל שגיאות רשת ו-429. אם OpenLibrary מחזיר 429 בדף 3 מתוך 10, הפונקציה מחזירה `total=40` במקום 100 — בלי שגיאה, בלי התראה. הטסט מאמת count שגוי ועובר ב-green.

**שגיאה:** אין שגיאה גלויה — הטסט עובר עם ספירה שגויה.

**תיקון:** לתפוס רק `PlaywrightTimeoutError` (selector לא נמצא = סוף הרשימה), ולתת לשאר לעלות:
```python
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

try:
    await self.page.wait_for_selector(self.BOOK_ITEMS, timeout=15000)
except PlaywrightTimeoutError:
    break  # אין ספרים בדף — סוף הרשימה
```
