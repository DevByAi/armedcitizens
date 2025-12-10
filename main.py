# ==================================
# קובץ: main.py (עם מקלדת צפה קבועה ו-Polling קשיח)
# ==================================
import os
import logging
from datetime import datetime, time
import pytz
import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler, 
    filters, 
    ChatMemberHandler,
    CallbackQueryHandler
)
from dotenv import load_dotenv

from db_models import init_db
from handlers.verification import handle_new_member, setup_verification_flow
from handlers.admin import setup_admin_handlers, set_admin_command 
from handlers.selling import setup_selling_handlers
from handlers.utils import check_user_status_and_reply # *** ייבוא הפונקציה החדשה ***

# דרוש ייבוא של הפונקציה schedule_weekly_posts
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

async def handle_main_keyboard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """מטפל בלחיצות על המקלדת הצפה הראשית."""
    query = update.callback_query
    await query.answer() 
    
    if query.data == "start_sell_flow":
        await context.bot.send_message(
            chat_id=query.message.chat_id, 
            text="מתחילים את תהליך פרסום המכירה. אנא שלח את פרטי המודעה."
        )
        # אם ה-selling handler מוגדר כ-ConversationHandler, הוא צריך לזהות את הפקודה הבאה.
        
    elif query.data == "check_verification_status":
        # *** קריאה לפונקציית הסטטוס החדשה ***
        await check_user_status_and_reply(query.message, context)
        
    elif query.data == "help_menu_main":
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="עזרה ראשית: פקודות ניהול נשלחות בנפרד. להלן אפשרויות המשתמש הראשי."
        )
        
    # משחזר את המקלדת
    await query.message.reply_text(
        "בחר אפשרות נוספת:",
        reply_markup=get_main_keyboard()
    )


async def show_main_keyboard_on_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """שולח מחדש את המקלדת הצפה בכל הודעת טקסט לא מזוהה בפרטי."""
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
    
    # *** 2. Handler לטיפול בלחיצות כפתור במקלדת הקבועה ***
    application.add_handler(CallbackQueryHandler(handle_main_keyboard_callback, pattern="^(start_sell_flow|check_verification_status|help_menu_main)$"))

    # 3. Handler גנרי למקלדת הקבועה
    application.add_handler(MessageHandler(
        filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND,
        show_main_keyboard_on_private_message
    ))

    application.add_handler(MessageHandler(
        filters.StatusUpdate.NEW_CHAT_MEMBERS | filters.StatusUpdate.LEFT_CHAT_MEMBER,
        delete_system_messages,
        block=True
    ))

    # 4. Handlers מודולריים
    application.add_handler(ChatMemberHandler(handle_new_member, ChatMemberHandler.CHAT_MEMBER))
    setup_verification_flow(application)
    setup_admin_handlers(application)
    setup_selling_handlers(application)
    
    # 5. רישום משימות מתוזמנות
    try:
        schedule_weekly_posts(application.job_queue) 
    except Exception as e:
        logger.warning(f"Error registering jobs: {e}. Skipping internal jobs.")
    
    # 6. הפעלת Polling קשיח
    try:
        logger.info("Starting bot in Polling mode...")
        application.run_polling(drop_pending_updates=True) 
        
    except telegram.error.TelegramError as e:
        logger.critical(f"FATAL TELEGRAM ERROR during Polling: {e}")
    except Exception as e:
        logger.critical(f"Unhandled exception during runtime: {e}")

if __name__ == '__main__':
    main()
