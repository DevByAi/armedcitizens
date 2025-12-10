# ==================================
# קובץ: handlers/verification.py (מלא)
# ==================================
import logging
from telegram import Update, ForceReply, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    ChatMemberHandler
)
import telegram

from db_operations import get_user, create_or_update_user
from handlers.utils import (
    restrict_user_permissions, 
    build_main_menu, 
    get_menu_text, 
    ALL_COMMUNITY_CHATS,
    ADMIN_CHAT_ID,
    add_back_button
)

logger = logging.getLogger(__name__)

# --- Conversation States ---
AWAITING_NAME, AWAITING_PHONE, AWAITING_LICENSE = range(3)


# --- Handlers ---

async def handle_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    מטפל בהצטרפות משתמשים חדשים לקבוצות הקהילה.
    מגביל את המשתמש ושולח הודעת ברוכים הבאים בפרטי.
    """
    chat_member = update.chat_member
    new_member = chat_member.new_chat_member
    
    if new_member.status == telegram.constants.ChatMemberStatus.MEMBER:
        user_id = new_member.user.id
        user = get_user(user_id)
        
        # 1. הגבלת הרשאות בקבוצה (אם לא מאושר)
        if not (user and user.is_approved):
            try:
                await restrict_user_permissions(chat_member.chat.id, user_id)
            except Exception as e:
                logger.error(f"Failed to restrict user {user_id} in chat {chat_member.chat.id}: {e}")
        
        # 2. שליחת הודעת אימות פרטית (אם המשתמש עדיין לא מאומת)
        if not (user and user.is_approved):
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="ברוך הבא! כדי לקבל גישה מלאה לקבוצות הקהילה, עליך לעבור תהליך אימות קצר. אנא התחל באמצעות /verify."
                )
            except Exception:
                logger.warning(f"Failed to send private welcome message to user {user_id}")


async def verify_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """מתחיל את שיחת האימות."""
    if update.effective_chat.type != "private":
        return ConversationHandler.END

    user = get_user(update.effective_user.id)
    if user and user.is_approved:
        await update.message.reply_text("✅ אתה כבר מאושר. אין צורך באימות נוסף.")
        return ConversationHandler.END

    await update.message.reply_text(
        "שלב 1/3: אנא שלח את שמך המלא כפי שמופיע בתעודת הזהות/רישיון."
    )
    return AWAITING_NAME


async def verify_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """שומר את השם ומבקש מספר טלפון."""
    context.user_data['full_name'] = update.message.text
    await update.message.reply_text(
        "שלב 2/3: אנא שלח את מספר הטלפון הנייד שלך (לדוגמה: 05X-XXXXXXX)."
    )
    return AWAITING_PHONE


async def verify_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """שומר את הטלפון ומבקש תמונת רישיון."""
    context.user_data['phone_number'] = update.message.text
    await update.message.reply_text(
        "שלב 3/3: אנא שלח תמונה ברורה של רישיון הנשק/התעודה שלך (ניתן לטשטש פרטים מזהים שאינם השם).",
        reply_markup=ForceReply(selective=True)
    )
    return AWAITING_LICENSE


async def verify_license(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """שומר את התמונה ומסיים את השיחה, שולח לאדמין."""
    
    if not update.message.photo:
        await update.message.reply_text("אנא שלח תמונה בלבד.")
        return AWAITING_LICENSE
    
    photo_file_id = update.message.photo[-1].file_id
    
    user_id = update.effective_user.id
    full_name = context.user_data.get('full_name')
    phone_number = context.user_data.get('phone_number')
    
    # 1. שמירת הנתונים ב-DB
    create_or_update_user(
        user_id, 
        full_name=full_name, 
        phone_number=phone_number, 
        license_photo_id=photo_file_id, 
        is_approved=False # מחכים לאישור אדמין
    )
    
    # 2. שליחה לאדמין לאישור
    message_to_admin = f"""🔔 בקשת אימות חדשה:

    👤 שם: {full_name}
    📱 טלפון: {phone_number}
    🆔 Telegram ID: `{user_id}`
    """
    
    keyboard = [
        [
            InlineKeyboardButton("✅ אשר", callback_data=f"approve_{user_id}"),
            InlineKeyboardButton("❌ דחה (חסום)", callback_data=f"ban_{user_id}")
        ]
    ]

    try:
        await context.bot.send_photo(
            chat_id=int(ADMIN_CHAT_ID),
            photo=photo_file_id,
            caption=message_to_admin,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Failed to send verification request to admin chat {ADMIN_CHAT_ID}: {e}")

    # 3. תגובה למשתמש
    await update.message.reply_text(
        "✅ הפרטים נשלחו בהצלחה! אנא המתן לאישור של מנהל הקהילה (עד 24 שעות).",
        reply_markup=build_main_menu() # מחזיר את המקלדת הראשית
    )
    
    # ניקוי נתוני השיחה
    context.user_data.clear()
    return ConversationHandler.END


async def verify_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """מסיים את השיחה עקב ביטול."""
    await update.message.reply_text(
        "🔄 האימות בוטל.",
        reply_markup=build_main_menu()
    )
    context.user_data.clear()
    return ConversationHandler.END


def setup_verification_flow(application: Application):
    """רושם את כל ה-Handlers של מודול האימות."""
    
    # Conversation Handler לאימות
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("verify", verify_start)],
        states={
            AWAITING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, verify_name)],
            AWAITING_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, verify_phone)],
            AWAITING_LICENSE: [MessageHandler(filters.PHOTO, verify_license)],
        },
        fallbacks=[CommandHandler('cancel', verify_cancel)],
        allow_reentry=True,
        per_user=True
    )
    
    application.add_handler(conv_handler)
    logger.info("Verification flow setup complete")
