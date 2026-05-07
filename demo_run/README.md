# Demo Run — 06.05.2026

ריצת דמו מלאה של הפרויקט. כל הקבצים כאן הם snapshot של ריצה אמיתית.

## תכולה

| קובץ / תיקייה | תיאור |
|---|---|
| `report.html` | דוח HTML מלא — פתח בדפדפן |
| `performance_report.json` | מדדי זמן טעינה לכל עמוד |
| `screenshots/` | צילומי מסך — ספרים שנוספו + כישלונות |

## screenshots

| קובץ | מה זה |
|---|---|
| `https___openlibrary_org_works_OL893415W_Dune_*.png` | Dune — נוסף לרשימת הקריאה |

## תוצאות ביצועים

| עמוד | זמן | סף |
|---|---|---|
| Search | 12,189ms | 3,000ms |
| Book | 3,774ms | 2,500ms |
| Reading List | 3,234ms | 2,000ms |

> כל העמודים מעל הסף — שרת חיצוני, ללא שליטה.

## Traces

| קובץ | תיאור |
|---|---|
| `traces/full_flow.zip` | Trace מלא של `test_full_flow` — חיפוש + הוספה לרשימה |

להפעלה: `npx playwright show-trace demo_run/traces/full_flow.zip`

שאר ה-Traces (~12MB) נוצרים ב-`reports/traces/` ולא מועלים לגיט.
