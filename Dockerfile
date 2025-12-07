# ====================================================================
# קובץ: Dockerfile (סופי)
# מותאם ל-Python 3.8 ופותר בעיות קומפילציה/נתיבים.
# ====================================================================

# --------------------------------------------------------------------
# שלב 1: שלב הבנייה (BUILDER STAGE)
# משתמש ב-Python 3.8 לבניית ספריות C (כמו ephem).
# --------------------------------------------------------------------
FROM python:3.8 as builder

# התקנת כלי בנייה נדרשים (build-essential כולל gcc)
RUN apt-get update && \
    apt-get install -y build-essential --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# הגדרת ספריית עבודה
WORKDIR /app

# העתקת דרישות והתקנה
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --------------------------------------------------------------------

# --------------------------------------------------------------------
# שלב 2: שלב הסיום (FINAL STAGE)
# משתמש ב-python:3.8-slim כדי לשמור על גודל קטן.
# --------------------------------------------------------------------
FROM python:3.8-slim

# הגדרת ספריית העבודה
WORKDIR /app

# **תיקון קריטי:** העתקת הספריות המותקנות מנתיב 3.8
COPY --from=builder /usr/local/lib/python3.8/site-packages /usr/local/lib/python3.8/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# העתקת קבצי הפרויקט שלך (כולל main.py, handlers/, ו-__init__.py)
# ודא שקובץ __init__.py קיים בתיקיית handlers/
COPY . .

# הגדרת הפורט הנדרש על ידי Railway/Cloud Run
ENV PORT 8080

# פקודת ההפעלה הראשית (Gunicorn)
# מריץ את main:app (האובייקט app מתוך main.py)
CMD exec gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 8 main:app
