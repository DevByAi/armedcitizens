# ==================================
# קובץ: handlers/selling.py (מלא)
# ==================================
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
    CallbackQueryHandler
)

from db_operations import add_sell_post, get_user_posts, get_sell_post, update_sell_post, delete_sell_post
from handlers.utils import is_user_approved, ALL_COMMUNITY_CHATS, ADMIN_CHAT_ID, add_back_button

logger = logging.getLogger(__name__)

# --- Conversation States ---
AWAITING_POST_CONTENT, AWAITING_EDIT_POST_ID, AWAITING_NEW_CONTENT = range(3)


# --- Handlers ---

async def sell_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """בודק הרשאה ומתחיל את שיחת המכירה."""
    user_id = update.effective_user.id

    if not is_user_approved(user_id):
        await update.message.reply_text("⛔️ עליך לעבור אימות מלא לפני פרסום מודעות.")
        return ConversationHandler.END

    await update.message.reply_text("אנא שלח את תוכן מודעת המכירה שלך.")
    return AWAITING_POST_CONTENT


async def sell_receive_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """שומר את תוכן המודעה ושולח לאדמין לאישור."""
    post_content = update.message.text
    user_id = update.effective_user.id

    # 1. שמירה ב-DB
    post = add_sell_post(user_id, post_content)
    
    # 2. שליחה לאדמין לאישור
    user = context.bot.get_chat_member(user_id, user_id).user
    
    message_to_admin = f"""📦 מודעת מכירה חדשה ממתינה:
    
    👤 מפרסם: {user.full_name} (@{user.username})
    🆔 Post ID: {post.id}

    📝 תוכן:
    {post_content}
    """
    
    keyboard = [
        [
            InlineKeyboardButton("✅ אשר מודעה", callback_data=f"approve_post_{post.id}"),
            InlineKeyboardButton("❌ דחה", callback_data=f"reject_post_{post.id}")
        ]
    ]

    try:
        await context.bot.send_message(
            chat_id=int(ADMIN_CHAT_ID),
            text=message_to_admin,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Failed to send selling post request to admin chat {ADMIN_CHAT_ID}: {e}")

    # 3. תגובה למשתמש
    await update.message.reply_text(
        f"✅ המודעה נשלחה לאישור מנהל (Post ID: {post.id}). תקבל הודעה לאחר אישור.",
        reply_markup=build_main_menu()
    )
    
    return ConversationHandler.END


async def sell_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """מסיים את השיחה עקב ביטול."""
    await update.message.reply_text(
        "🔄 יצירת המודעה בוטלה.",
        reply_markup=build_main_menu()
    )
    return ConversationHandler.END

# --- Edit Handlers Placeholder ---

async def edit_my_posts_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """מראה למשתמש את המודעות הפעילות שלו לבחירה."""
    user_id = update.effective_user.id
    
    if not is_user_approved(user_id):
        await update.message.reply_text("⛔️ עליך לעבור אימות מלא לפני עריכת מודעות.")
        return ConversationHandler.END
    
    posts = get_user_posts(user_id)
    
    if not posts:
        await update.message.reply_text("אין לך מודעות פעילות לערוך.")
        return ConversationHandler.END
        
    text = "בחר את המודעה לעריכה:\n"
    keyboard = []
    
    for post in posts:
        is_pending = " (ממתין לאישור)" if not post.is_approved_by_admin else ""
        keyboard.append([
            InlineKeyboardButton(
                f"ID {post.id}: {post.content[:30]}...{is_pending}",
                callback_data=f"edit_post_select_{post.id}"
            )
        ])
        
    keyboard = add_back_button(keyboard)

    await update.message.reply_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END # למעשה, זה יעבור ל-CallbackHandler


def setup_selling_handlers(application: Application):
    """רושם את כל ה-Handlers של מודול המכירה."""
    
    # 1. יצירת מודעה חדשה
    sell_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("sell", sell_start)],
        states={
            AWAITING_POST_CONTENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, sell_receive_content)],
        },
        fallbacks=[CommandHandler('cancel', sell_cancel)],
        allow_reentry=True,
        per_user=False # יכול להיות פאלס מכיוון שזו שיחה קצרה
    )
    application.add_handler(sell_conv_handler)
    
    # 2. עריכת מודעה קיימת (שיחה נפרדת או כניסה מתוך callback)
    # נניח שפקודה /edit פותחת את תהליך העריכה
    application.add_handler(CommandHandler("editposts", edit_my_posts_start))

    logger.info("Selling handlers setup complete")
