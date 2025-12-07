# ==================================
# קובץ: main.py (הגרסה המעודכנת ל-Webhooks)
# ==================================
import os
import logging
import asyncio
from datetime import datetime, time
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ChatMemberHandler
from dotenv import load_dotenv

from db_models import init_db
from handlers.verification import handle_new_member, setup_verification_flow
from handlers.admin import setup_admin_handlers
from handlers.selling import setup_selling_handlers

ISRAEL_TZ = pytz.timezone('Asia/Jerusalem')

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_URL = os.getenv("DATABASE_URL") or os.getenv("DB_URL")

PORT = int(os.environ.get("PORT", 5000))
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

async def delete_system_messages(update, context):
    if update.message and (update.message.new_chat_members or update.message.left_chat_member):
        try:
            await update.message.delete()
        except Exception:
            logger.warning("Failed to delete system message. Check bot permissions.")


async def ask_relevance_job(context):
    """Daily job at 9am Israel time - asks users to confirm post relevance for the week."""
    from db_operations import get_posts_needing_relevance_check, reset_weekly_relevance
    from handlers.utils import DAY_NAMES
    
    reset_weekly_relevance()
    
    posts = get_posts_needing_relevance_check()
    
    for post in posts:
        try:
            day_name = DAY_NAMES.get(post.publication_day, "לא נבחר")
            keyboard = [
                [
                    InlineKeyboardButton("כן, רלוונטי ✅", callback_data=f"confirm_relevant_{post.id}"),
                    InlineKeyboardButton("לא רלוונטי ❌", callback_data=f"not_relevant_{post.id}")
                ]
            ]
            
            await context.bot.send_message(
                chat_id=post.user_id,
                text=f"📦 האם המודעה שלך עדיין רלוונטית השבוע?\n\n"
                     f"📅 יום פרסום: {day_name}\n"
                     f"📝 תוכן:\n{post.content[:200]}...\n\n"
                     f"אנא אשר שהמודעה רלוונטית לפרסום השבוע:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Failed to ask relevance for post {post.id}: {e}")
    
    logger.info(f"Asked relevance for {len(posts)} posts")


async def publish_posts_job(context):
    """Hourly job (8am-10pm, not Shabbat) - publishes posts scheduled for this hour."""
    from db_operations import get_posts_for_hour, mark_post_sent
    from handlers.utils import ALL_COMMUNITY_CHATS
    
    now = datetime.now(ISRAEL_TZ)
    day_of_week = now.weekday()
    hour = now.hour
    
    # Python weekday(): 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
    if day_of_week == 4:  # Friday
        if hour >= 14:
            logger.info("Skipping publish - Friday after 2pm (Shabbat)")
            return
    elif day_of_week == 5:  # Saturday
        logger.info("Skipping publish - Saturday (Shabbat)")
        return
    
    if hour < 8 or hour > 22:
        logger.info("Skipping publish - outside 8am-10pm window")
        return
    
    # Convert Python weekday to our day system (0=Sunday, 1=Monday, ..., 5=Friday)
    # Python: 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
    # Our system: 0=Sun, 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri
    if day_of_week == 6:  # Sunday
        today_day = 0
    else:
        today_day = day_of_week + 1
    
    posts = get_posts_for_hour(today_day, hour)
    
    if not posts:
        logger.info(f"No posts to publish for day {today_day} at hour {hour}")
        return
    
    for post in posts:
        for chat_id in ALL_COMMUNITY_CHATS:
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"📦 מודעת מכירה:\n\n{post.content}"
                )
            except Exception as e:
                logger.error(f"Failed to publish post {post.id} to chat {chat_id}: {e}")
        
        mark_post_sent(post.id)
        logger.info(f"Published post {post.id} at hour {hour}")
    
    logger.info(f"Published {len(posts)} posts at hour {hour}")


def main():
    if not BOT_TOKEN or not DB_URL:
        logger.critical("Missing BOT_TOKEN or DATABASE_URL in environment.")
        return

    init_db(DB_URL)
    
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    application.add_handler(MessageHandler(
        filters.StatusUpdate.NEW_CHAT_MEMBERS | filters.StatusUpdate.LEFT_CHAT_MEMBER,
        delete_system_messages,
        block=True
    ))

    application.add_handler(ChatMemberHandler(handle_new_member, ChatMemberHandler.CHAT_MEMBER))
    setup_verification_flow(application)
    setup_admin_handlers(application)
    setup_selling_handlers(application)
    
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
    
    if WEBHOOK_URL:
        logger.info(f"Starting webhook on port {PORT}")
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=WEBHOOK_PATH,
            webhook_url=WEBHOOK_URL + WEBHOOK_PATH
        )
    else:
        logger.info("No WEBHOOK_URL set, running in polling mode")
        application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
