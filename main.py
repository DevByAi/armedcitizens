# ==================================
# קובץ: main.py (עם מקלדת צפה קבועה ו-Polling קשיח)
# ==================================
import os
import logging
from datetime import datetime, time
import pytz
import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup # ייבוא InlineKeyboard
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler, 
    filters, 
    ChatMemberHandler
)
from dotenv import load_dotenv

from db_models import init_db
from handlers.verification import handle_new_member, setup_verification_flow
from handlers.admin import setup_admin_handlers, set_admin_command 
from handlers.selling import setup_selling_handlers
try:
    from handlers.jobs import schedule_weekly_posts
except ImportError:
    def schedule_weekly_posts(job_queue): pass 
    

ISRAEL_TZ = pytz.timezone('Asia/Jerusalem')

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_URL = os.getenv("DATABASE_URL") or os.getenv("DB_URL")

PORT = int(os.environ.get("PORT", 5000))
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# פונקציית המקלדת הצפה הראשית
# ----------------------------------------------------------------------

def get_main_keyboard():
    """מחזיר את המקלדת הצפה הראשית."""
    keyboard = [
        [InlineKeyboardButton("📦 מכירה חדשה", callback_data="start_sell_flow")],
        [InlineKeyboardButton("👤 מצב אימות", callback_data="check_verification_status")],
        [InlineKeyboardButton("❓ עזרה ופקודות", callback_data="help_menu_main")]
    ]
    return InlineKeyboardMarkup(keyboard)


# ----------------------------------------------------------------------
# Handlers
# ----------------------------------------------------------------------

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """שולח הודעת התחלה בסיסית עם המקלדת הצפה בפרטי."""
    if update.effective_chat.type == "private":
        await update.message.reply_text(
            "שלום! בחר פעולה מהתפריט הראשי:",
            reply_markup=get_main_keyboard()
        )
    # בקבוצות הבוט מתעלם (כפי שרצית)

async def show_main_keyboard_on_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """שולח מחדש את המקלדת הצפה בכל הודעת טקסט לא מזוהה בפרטי."""
    # מוודאים שזו הודעה פרטית, שאינה פקודה
    if update.effective_chat.type == "private":
        await update.message.reply_text(
            "אנא בחר אפשרות מהתפריט הראשי:",
            reply_markup=get_main_keyboard()
        )

async def delete_system_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and (update.message.new_chat_members or update.message.left_chat_member):
        try:
            await update.message.delete()
        except Exception:
            logger.warning("Failed to delete system message. Check bot permissions.")


async def ask_relevance_job(context):
    """Daily job at 9am Israel time - asks users to confirm post relevance for the week."""
    from db_operations import get_posts_needing_relevance_check, reset_weekly_relevance
    # ... (המשך הלוגיקה של הג'ובים)
    pass 

async def publish_posts_job(context):
    """Hourly job (8am-10pm, not Shabbat) - publishes posts scheduled for this hour."""
    # ... (המשך הלוגיקה של הג'ובים)
    pass 


def main():
    if not BOT_TOKEN or not DB_URL:
        logger.critical("Missing BOT_TOKEN or DATABASE_URL in environment.")
        return

    try:
        init_db(DB_URL)
    except Exception as e:
        logger.critical(f"Failed to initialize database: {e}")
        return
    
    application = telegram.ext.Application.builder().token(BOT_TOKEN).build()
    
    # 1. Handlers בסיסיים
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("set_admin", set_admin_command)) 

    # 2. Handler גנרי למקלדת הקבועה (בצ'אטים פרטיים בלבד, לא פקודות)
    application.add_handler(MessageHandler(
        filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND,
        show_main_keyboard_on_private_message
    ))

    application.add_handler(MessageHandler(
        filters.StatusUpdate.NEW_CHAT_MEMBERS | filters.StatusUpdate.LEFT_CHAT_MEMBER,
        delete_system_messages,
        block=True
    ))

    # 3. Handlers מודולריים
    application.add_handler(telegram.ext.ChatMemberHandler(handle_new_member, telegram.ext.ChatMemberHandler.CHAT_MEMBER))
    setup_verification_flow(application)
    setup_admin_handlers(application)
    setup_selling_handlers(application)
    
    # 4. רישום משימות מתוזמנות
    try:
        from handlers.jobs import schedule_weekly_posts
        schedule_weekly_posts(application.job_queue) 
    except ImportError:
        # אם קובץ jobs.py עדיין חסר, נשתמש ברישום הג'ובים הפנימי כפאלבק
        job_queue = application.job_queue
        job_queue.run_daily(
            ask_relevance_job,
            time=time(hour=9, minute=0, tzinfo=ISRAEL_TZ),
            name="ask_relevance"
        )
        job_queue.run_repeating(
            publish_posts_job,
            interval=3600,
            first=10,
            name="publish_posts"
        )
    logger.info("Scheduled jobs registered")
    
    # *** 5. הפעלת Polling קשיח (עבור Worker) ***
    if WEBHOOK_URL and os.getenv("RENDER_EXTERNAL_URL"):
         logger.warning("Ignoring WEBHOOK_URL, running Polling in Worker Service.")
         
    try:
        logger.info("Starting bot in Polling mode...")
        # הפעלה במצב Polling, עם מחיקת עדכונים ישנים
        application.run_polling(drop_pending_updates=True) 
        
    except telegram.error.TelegramError as e:
        logger.critical(f"FATAL TELEGRAM ERROR during Polling: {e}")
    except Exception as e:
        logger.critical(f"Unhandled exception during runtime: {e}")

if __name__ == '__main__':
    main()
