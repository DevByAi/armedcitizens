# ==================================
# Stage 1: Builder
# ==================================
# משתמשים באימג' המלא להתקנת חבילות הדורשות קומפילציה (כמו psycopg2)
FROM python:3.8 AS builder

# מתקינים כלי בנייה נדרשים
RUN apt-get update && \
    apt-get install -y build-essential --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# מעתיקים קובץ דרישות ומתקינים
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# ==================================
# Stage 2: Runtime (האימג' הסופי)
# ==================================
# משתמשים באימג' הקל (slim) לזמן ריצה כדי להקטין את גודל האימג'
FROM python:3.8-slim AS stage-1

WORKDIR /app

# מעתיקים את הספריות שהותקנו בשלב ה-builder
COPY --from=builder /usr/local/lib/python3.8/site-packages /usr/local/lib/python3.8/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# מעתיקים את שאר קבצי היישום (main.py, db_operations.py, וכו')
COPY . .

# פקודת ההפעלה הקריטית:
# במקום להפעיל את Gunicorn (שמחפש 'app'), אנו מריצים את הסקריפט main.py ישירות
# הפקודה הזו דורסת כל הגדרה קודמת של Gunicorn
CMD ["python", "main.py"]
