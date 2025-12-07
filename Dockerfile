# ==================================
# קובץ: Dockerfile (סופי)
# ==================================
# שלב 1: שלב הבנייה
FROM python:3.8 as builder

# התקנת כלי בנייה נדרשים
RUN apt-get update && \
    apt-get install -y build-essential --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# העתקת דרישות והתקנה
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# שלב 2: שלב הסיום
FROM python:3.8-slim

# הגדרת ספריית העבודה
WORKDIR /app

# העתקת הספריות המותקנות מהשלב הקודם
COPY --from=builder /usr/local/lib/python3.8/site-packages /usr/local/lib/python3.8/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# העתקת קבצי הפרויקט שלך
COPY . .

# פקודת ההפעלה הראשית (עבור Background Worker)
# דורסת Gunicorn ומריצה את main.py ישירות
CMD ["python", "main.py"]
