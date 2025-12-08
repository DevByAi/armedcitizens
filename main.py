# ==================================
# קובץ: main.py (מתוקן סופית)
# ==================================
import os
import logging
from datetime import datetime, time
import pytz
from telegram import Update
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
from handlers.admin import setup_admin_handlers, set_admin_command # ייבוא set_admin_command
from handlers.selling import setup_selling_handlers
from handlers.jobs import schedule_weekly_posts # פונקציה לרישום ג'ובס

ISRAEL_TZ = pytz.timezone('Asia/Jerusalem')

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_URL = os.getenv("DATABASE_URL") or os.getenv("DB_URL")
# נדרש גם: SUPER_ADMIN_ID

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """שולח הודעת התחלה בסיסית."""
    if update.effective_chat.type == "private":
        await update.message.reply_text("שלום! אני בוט הקהילה. אנא המתן לאישור אדמין.")

async def delete_system_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and (update.message.new_chat_members or update.message.left_chat_member):
        try:
            await update.message.delete()
        except Exception:
            logger.warning("Failed to delete system message. Check bot permissions.")
            
def main():
    if not BOT_TOKEN or not DB_URL:
        logger.critical("Missing BOT_TOKEN or DATABASE_URL in environment.")
        return

    # *** התיקון הקריטי: העברת DB_URL ל-init_db ***
    try:
        init_db(DB_URL) 
    except Exception as e:
        logger.critical(f"Failed to initialize database: {e}")
        return
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Handlers בסיסיים
    application.add_handler(CommandHandler("start", start_command))
    # *** הוספת ה-HANDLER של set_admin כאן! ***
    application.add_handler(CommandHandler("set_admin", set_admin_command)) 

    application.add_handler(MessageHandler(
        filters.StatusUpdate.NEW_CHAT_MEMBERS | filters.StatusUpdate.LEFT_CHAT_MEMBER,
        delete_system_messages,
        block=True
    ))
    
    # Handlers לאימות משתמשים חדשים
    application.add_handler(ChatMemberHandler(handle_new_member, ChatMemberHandler.CHAT_MEMBER))
    setup_verification_flow(application)
    
    # Handlers לאדמינים ולמכירות
    setup_admin_handlers(application)
    setup_selling_handlers(application)
    
    # רישום משימות מתוזמנות
    # הפונקציה schedule_weekly_posts (שמייבאת את הג'ובס)
    schedule_weekly_posts(application.job_queue) 
    logger.info("Scheduled jobs registered")
    
    # *** הפעלת הבוט במצב Polling ***
    logger.info("Starting bot in Polling mode...")
    application.run_polling(drop_pending_updates=True)


if __name__ == '__main__':
    main()
