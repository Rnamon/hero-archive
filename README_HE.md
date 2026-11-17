# THE HERO ARCHIVE – מדריך קצר

## לפתוח ולבדוק עכשיו
לחץ פעמיים על `index.html`. זה עובד בלי אינטרנט. הנתונים האמיתיים כבר בתוך הדף.
האוסף שלך נשמר בדפדפן הזה בלבד – לכן יש כפתור גיבוי ב"Data & backup".

## מה בתיקייה
- `index.html` – האפליקציה (נתונים אמיתיים בתוכה, כגיבוי).
- `data/hero-data.json` – הנתונים המסודרים. כשהדף עולה ל-GitHub Pages הוא קורא קודם את הקובץ הזה.
- `images/` – תמונות קטנות וגדולות. ריקה כרגע; סקריפט ההורדה ימלא אותה (כל תמונה יורדת פעם אחת בלבד).
- `raw/` – הקבצים המקוריים שלך (cardinfo + cardsets), בלי שינוי.
- `scripts/build_data.py` – הופך את `raw/` ל-`data/hero-data.json` ומעדכן את הנתונים שבתוך הדף.
- `scripts/fetch_sources.py` – מוריד קבצים חדשים מ-YGOPRODeck. **לא נבדק** (לא היה לי אינטרנט).
- `.github/workflows/update-data.yml` – מריץ את שני הסקריפטים פעם ביום ב-GitHub. **לא נבדק**.

## להעלות ל-GitHub Pages (כשתרצה)
1. צור repo חדש ב-GitHub והעלה אליו את כל התוכן של התיקייה הזו (כולל התיקייה `.github`).
2. ב-repo: Settings → Pages → Source: "Deploy from a branch" → Branch: `main`, תיקייה `/ (root)` → Save.
3. אחרי דקה-שתיים הכתובת תופיע שם.
4. לבדיקת העדכון האוטומטי: Actions → "Update card data" → Run workflow. אם זה נכשל, תעתיק לי את השגיאה.

## לעדכן ידנית במחשב
```
python3 -I scripts/fetch_sources.py raw
python3 -I scripts/build_data.py --cards raw/cardinfo.json --sets raw/cardsets.json --out data/hero-data.json --html index.html
```
