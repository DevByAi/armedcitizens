import os
import telegram
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
import logging
from dotenv import load_dotenv

# ייבוא מודולים מקומיים
from db_operations import init_db
from handlers.verification import setup_verification_flow
from handlers.admin import setup_admin_handlers
from handlers.selling import setup_selling_handlers
from handlers.jobs import schedule_weekly_posts

# טעינת משתני סביבה
load_dotenv()

# הגדרת לוגר
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# קבלת משתני סביבה
BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_URL = os.getenv("DB_URL")
# ההגדרות הבאות אינן נחוצות למצב Polling, אך חשוב לוודא שהן קיימות כערך כלשהו
# למקרה שהקוד משתמש בהן לפני run_polling
ADMIN_CHANNEL_ID = os.getenv("ADMIN_CHANNEL_ID", 0) 
SELL_GROUP_ID = os.getenv("SELL_GROUP_ID", 0)
ALL_COMMUNITY_CHATS = os.getenv("ALL_COMMUNITY_CHATS", "")
# WEBHOOK_URL ו-PORT אינם בשימוש במצב Polling

# ----------------------------------------------------------------------
# פונקציות בסיסיות (Start)
# ----------------------------------------------------------------------

async def start_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """שולח הודעת התחלה בסיסית."""
    if update.effective_chat.type == "private":
        await update.message.reply_text("שלום! אני בוט הקהילה. אנא המתן לאישור אדמין.")
    else:
        # התעלם מפקודת /start בצ'אטים קבוצתיים
        pass

# ----------------------------------------------------------------------
# פונקציית MAIN - נקודת הכניסה לבוט
# ----------------------------------------------------------------------

def main() -> None:
    # 1. בדיקת BOT_TOKEN
    if not BOT_TOKEN:
        logger.critical("BOT_TOKEN is missing! Cannot start bot.")
        return

    # 2. אתחול בסיס נתונים (init_db פועל כעת)
    try:
    init_db()  # <--- פשוט קוראים לה ללא ארגומנטים
except Exception as e:
        logger.critical(f"Failed to initialize database: {e}")
        return

    # 3. בניית האפליקציה
    application = Application.builder().token(BOT_TOKEN).build()
    
    # 4. הגדרת Handlers
    
    # Handlers בסיסיים
    application.add_handler(CommandHandler("start", start_command))
    
    # Handlers לאימות משתמשים חדשים
    setup_verification_flow(application)
    logger.info("Verification flow setup complete")
    
    # Handlers לאדמינים
    setup_admin_handlers(application)
    logger.info("Admin handlers setup complete")

    # Handlers למכירות ופרסומים
    setup_selling_handlers(application)
    logger.info("Selling handlers setup complete")

    # 5. רישום משימות מתוזמנות
    schedule_weekly_posts(application.job_queue)
    logger.info("Scheduled jobs registered")
    
    # 6. הפעלת הבוט
    
    # *** התיקון הקריטי: מעבר ל-Polling עבור Worker Service ***
    try:
        logger.info("Starting bot in Polling mode...")
        application.run_polling()
        
    except telegram.error.TelegramError as e:
        logger.critical(f"FATAL TELEGRAM ERROR during Polling: {e}")
    except Exception as e:
        logger.critical(f"Unhandled exception during runtime: {e}")

if __name__ == "__main__":
    main()
