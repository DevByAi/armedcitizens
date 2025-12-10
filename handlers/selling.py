# ==================================
# קובץ: handlers/selling.py (מלא ומתוקן - כפתור עובד)
# ==================================
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    CommandHandler
)

from db_operations import add_sell_post, get_user_posts, get_sell_post, update_sell_post, delete_sell_post
from handlers.utils import is_user_approved, ALL_COMMUNITY_CHATS, ADMIN_CHAT_ID, build_main_menu_for_user, add_back_button

logger = logging.getLogger(__name__)

# --- Conversation States ---
AWAITING_POST_CONTENT, AWAITING_EDIT_POST_ID, AWAITING_NEW_CONTENT = range(3)


# --- Handlers ---

async def sell_start_check(update: Update, user_id: int) -> bool:
    """בדיקת עזר האם למשתמש מותר לפרסם."""
    if not is_user_approved(user_id):
        # הודעה למשתמש
        message = update.message if update.message else update.callback_query.message
        await message.reply_text("⛔️ עליך לעבור אימות מלא לפני פרסום מודעות.")
        return False
    return True

async def sell_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """מתחיל את שיחת המכירה דרך פקודה /sell."""
    if not await sell_start_check(update, update.effective_user.id):
        return ConversationHandler.END

    await update.message.reply_text("✏️ אנא שלח כעת את תוכן מודעת המכירה שלך (טקסט/תמונה):")
    return AWAITING_POST_CONTENT

async def sell_start_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """מתחיל את שיחת המכירה דרך כפתור המקלדת."""
    query = update.callback_query
    await query.answer()
    
    if not await sell_start_check(update, query.from_user.id):
        return ConversationHandler.END

    await query.message.reply_text("✏️ אנא שלח כעת את תוכן מודעת המכירה שלך (טקסט/תמונה):")
    return AWAITING_POST_CONTENT


async def sell_receive_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """שומר את תוכן המודעה ושולח לאדמין לאישור."""
    
    # תמיכה בטקסט או תמונה עם כיתוב
    if update.message.photo:
        post_content = update.message.caption or "[תמונה ללא טקסט]"
        # כאן אפשר להוסיף לוגיקה לשמירת ה-File ID של התמונה ב-DB אם רוצים
    else:
        post_content = update.message.text

    if not post_content:
        await update.message.reply_text("⚠️ אנא שלח טקסט או תמונה עם כיתוב.")
        return AWAITING_POST_CONTENT

    user_id = update.effective_user.id

    # 1. שמירה ב-DB
    post = add_sell_post(user_id, post_content)
    
    # 2. שליחה לאדמין לאישור
    telegram_user = update.effective_user
    full_name = telegram_user.full_name or "לא צוין שם"
    username = f"@{telegram_user.username}" if telegram_user.username else "אין Username"
    
    message_to_admin = f"""📦 **מודעת מכירה חדשה ממתינה:**
    
👤 מפרסם: {full_name} ({username})
🆔 Post ID: `{post.id}`

📝 **תוכן:**
{post_content}
    """
    
    keyboard = [
        [
            InlineKeyboardButton("✅ אשר מודעה", callback_data=f"approve_post_{post.id}"),
            InlineKeyboardButton("❌ דחה", callback_data=f"reject_post_{post.id}")
        ]
    ]

    try:
        # אם יש תמונה, נשלח תמונה. אם לא, טקסט.
        if update.message.photo:
             await context.bot.send_photo(
                chat_id=int(ADMIN_CHAT_ID),
                photo=update.message.photo[-1].file_id,
                caption=message_to_admin,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await context.bot.send_message(
                chat_id=int(ADMIN_CHAT_ID),
                text=message_to_admin,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
    except Exception as e:
        logger.error(f"Failed to send selling post to admin: {e}")
        await update.message.reply_text("❌ שגיאה בשליחת המודעה לאדמין. נסה שוב.")
        return ConversationHandler.END

    # 3. תגובה למשתמש
    await update.message.reply_text(
        f"✅ המודעה נשלחה לאישור מנהל (מספר מודעה: {post.id}).\nתקבל הודעה ברגע שהיא תאושר.",
        reply_markup=build_main_menu_for_user(user_id)
    )
    
    return ConversationHandler.END


async def sell_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """מסיים את השיחה עקב ביטול."""
    text = "🔄 יצירת המודעה בוטלה."
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(text, reply_markup=build_main_menu_for_user(update.effective_user.id))
    else:
        await update.message.reply_text(text, reply_markup=build_main_menu_for_user(update.effective_user.id))
        
    return ConversationHandler.END

# --- Edit Handlers Placeholder ---
async def edit_my_posts_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """(Placeholder) עריכת מודעות."""
    user_id = update.effective_user.id
    posts = get_user_posts(user_id)
    if not posts:
        await update.message.reply_text("אין לך מודעות פעילות.")
        return ConversationHandler.END
    await update.message.reply_text(f"יש לך {len(posts)} מודעות פעילות.")
    return ConversationHandler.END


def setup_selling_handlers(application: Application):
    """רושם את כל ה-Handlers של מודול המכירה."""
    
    # יצירת מודעה חדשה - גם בפקודה וגם בכפתור
    sell_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("sell", sell_start_command),
            CallbackQueryHandler(sell_start_button, pattern="^start_sell_flow$") # הטיפול בכפתור עבר לכאן
        ],
        states={
            AWAITING_POST_CONTENT: [
                MessageHandler(filters.TEXT | filters.PHOTO & ~filters.COMMAND, sell_receive_content)
            ],
        },
        fallbacks=[CommandHandler('cancel', sell_cancel)],
        allow_reentry=True
    )
    application.add_handler(sell_conv_handler)
    
    application.add_handler(CommandHandler("editposts", edit_my_posts_start))

    logger.info("Selling handlers setup complete")
