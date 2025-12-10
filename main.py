# ==================================
# קובץ: main.py (מלא וסופי - נקי)
# ==================================
import os
import logging
from datetime import datetime, time
import pytz
import telegram
from telegram import Update
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
from handlers.utils import check_user_status_and_reply, build_main_menu_for_user

try:
    from handlers.jobs import schedule_weekly_posts
except ImportError:
    def schedule_weekly_posts(job_queue): pass 

ISRAEL_TZ = pytz.timezone('Asia/Jerusalem')
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_URL = os.getenv("DATABASE_URL") or os.getenv("DB_URL")
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type == "private":
        await update.message.reply_text(
            "👋 שלום! ברוך הבא לבוט הקהילה.\nבחר פעולה מהתפריט:",
            reply_markup=build_main_menu_for_user(update.effective_user.id)
        )

async def handle_general_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """מטפל בכפתורים כלליים (חזרה, עזרה, סטטוס)."""
    query = update.callback_query
    # לא עושים query.answer() כאן אם רוצים שרשרת, אבל לרוב כדאי.
    # נשאיר את זה ל-Handlers הספציפיים או נעשה כאן אם ה-ID לא נתפס.
    
    if query.data == "check_verification_status":
        await query.answer()
        await check_user_status_and_reply(query.message, context)
        
    elif query.data == "help_menu_main":
        await query.answer()
        help_text = """📚 **עזרה ופקודות:**
        
✅ **אימות:** לחץ על "מצב אימות" כדי לראות אם אושרת.
📦 **מכירה:** לחץ על "מכירה חדשה" כדי לפרסם ציוד.
👮 **מנהלים:** יש לכם כפתורים נוספים לניהול המערכת.

לכל בעיה, פנה למנהלי הקבוצה.
"""
        await query.message.edit_text(help_text, parse_mode="Markdown", 
                                      reply_markup=build_main_menu_for_user(query.from_user.id))
    
    elif query.data == "main_menu_return":
        await query.answer()
        await query.message.edit_text(
            "תפריט ראשי:",
            reply_markup=build_main_menu_for_user(query.from_user.id)
        )

async def show_main_keyboard_on_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type == "private":
        await update.message.reply_text(
            "תפריט ראשי:",
            reply_markup=build_main_menu_for_user(update.effective_user.id)
        )

def main():
    if not BOT_TOKEN or not DB_URL:
        return

    try:
        init_db(DB_URL)
    except Exception as e:
        logger.critical(f"DB Error: {e}")
        return
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # 1. פקודות בסיס
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("set_admin", set_admin_command)) 

    # 2. Handlers מודולריים (שים לב לסדר!)
    # Selling חייב להיות לפני ה-General Callback כדי לתפוס את "start_sell_flow"
    setup_selling_handlers(application) 
    setup_admin_handlers(application)   # תופס את admin_stats וכו'
    
    # 3. Callback כללי (שאריות: עזרה, סטטוס, חזרה)
    application.add_handler(CallbackQueryHandler(handle_general_callbacks, pattern="^(check_verification_status|help_menu_main|main_menu_return)$"))

    # 4. הודעות טקסט (Echo UI)
    application.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & ~filters.COMMAND,
        show_main_keyboard_on_private_message
    ))

    setup_verification_flow(application)
    
    try:
        schedule_weekly_posts(application.job_queue)
    except:
        pass
    
    logger.info("Starting bot...")
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
