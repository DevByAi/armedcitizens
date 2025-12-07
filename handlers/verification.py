import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from db_operations import create_or_update_user, get_user
from handlers.utils import (
    restrict_user_permissions, grant_user_permissions, ADMIN_CHAT_ID,
    build_main_menu, build_back_button, add_back_button, get_menu_text
)

logger = logging.getLogger(__name__)

# Conversation states
AWAITING_NAME, AWAITING_PHONE, AWAITING_LICENSE = range(3)


async def handle_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles new chat members joining the group."""
    try:
        new_member = update.chat_member.new_chat_member
        if new_member.user.is_bot:
            return
        
        user_id = new_member.user.id
        chat_id = update.chat_member.chat.id
        
        # Check if user is already approved
        user = get_user(user_id)
        if user and user.is_approved and not user.is_banned:
            await grant_user_permissions(chat_id, user_id)
            return
        
        # Restrict new user permissions until verified
        await restrict_user_permissions(chat_id, user_id, can_write=False)
        
        # Send verification message (simplified stub)
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="ברוך הבא! אנא השלם את תהליך האימות על ידי מתן הפרטים הבאים.\n\nשלח את שמך המלא:"
            )
        except Exception as e:
            logger.warning(f"Could not send DM to user {user_id}: {e}")
            
    except Exception as e:
        logger.error(f"Error in handle_new_member: {e}")


async def start_verification(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the verification process."""
    user_id = update.effective_user.id
    
    await update.message.reply_text(
        get_menu_text(user_id),
        reply_markup=build_main_menu(user_id)
    )
    return ConversationHandler.END


async def start_verify_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback when user clicks start verification button."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("בוא נתחיל בתהליך האימות.\n\nמה שמך המלא?")
    return AWAITING_NAME


async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives user's full name."""
    context.user_data['full_name'] = update.message.text
    await update.message.reply_text("תודה! עכשיו שלח את מספר הטלפון שלך:")
    return AWAITING_PHONE


async def receive_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives user's phone number."""
    context.user_data['phone_number'] = update.message.text
    await update.message.reply_text("נהדר! עכשיו שלח תמונה של הרישיון שלך:")
    return AWAITING_LICENSE


async def receive_license(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives user's license photo and completes verification."""
    if not update.message.photo:
        await update.message.reply_text("אנא שלח תמונה של הרישיון.")
        return AWAITING_LICENSE
    
    photo = update.message.photo[-1]
    telegram_id = update.effective_user.id
    username = update.effective_user.username or "אין"
    full_name = context.user_data.get('full_name', '')
    phone_number = context.user_data.get('phone_number', '')
    
    # Save user data to database
    create_or_update_user(
        telegram_id=telegram_id,
        full_name=full_name,
        phone_number=phone_number,
        license_photo_id=photo.file_id,
        is_approved=False
    )
    
    await update.message.reply_text(
        "תודה! הפרטים שלך נשלחו לאישור. נעדכן אותך בהקדם.",
        reply_markup=build_back_button()
    )
    
    # Send details to admin channel with inline keyboard
    if ADMIN_CHAT_ID:
        try:
            admin_message = f"""🔔 בקשת אימות חדשה:

👤 שם: {full_name}
📱 טלפון: {phone_number}
🆔 Telegram ID: {telegram_id}
📛 Username: @{username}"""
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ אשר", callback_data=f"approve_{telegram_id}"),
                    InlineKeyboardButton("❌ דחה", callback_data=f"ban_{telegram_id}")
                ]
            ]
            
            await context.bot.send_photo(
                chat_id=int(ADMIN_CHAT_ID),
                photo=photo.file_id,
                caption=admin_message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Failed to send verification to admin: {e}")
    
    context.user_data.clear()
    return ConversationHandler.END


async def cancel_verification(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels the verification process."""
    await update.message.reply_text("תהליך האימות בוטל.")
    context.user_data.clear()
    return ConversationHandler.END


async def cancel_verify_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback when user clicks cancel verification."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("תהליך האימות בוטל. תוכל להתחיל שוב בכל עת עם /start")
    context.user_data.clear()
    return ConversationHandler.END


async def approve_user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback when admin clicks approve button."""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    target_user_id = int(callback_data.replace("approve_", ""))
    
    user = get_user(target_user_id)
    if not user:
        await query.edit_message_caption(
            caption=query.message.caption + "\n\n❌ משתמש לא נמצא במערכת."
        )
        return
    
    create_or_update_user(target_user_id, is_approved=True)
    
    from handlers.utils import grant_user_permissions, ALL_COMMUNITY_CHATS
    for chat_id in ALL_COMMUNITY_CHATS:
        try:
            await grant_user_permissions(chat_id, target_user_id)
        except Exception as e:
            logger.warning(f"Could not grant permissions in chat {chat_id}: {e}")
    
    await query.edit_message_caption(
        caption=query.message.caption + "\n\n✅ אושר על ידי " + query.from_user.first_name
    )
    
    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text="🎉 הבקשה שלך אושרה! כעת יש לך גישה לכל קבוצות הקהילה."
        )
    except Exception:
        pass


async def ban_user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback when admin clicks ban button."""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    target_user_id = int(callback_data.replace("ban_", ""))
    
    from handlers.utils import ban_user_globally
    await ban_user_globally(context.bot, target_user_id)
    
    await query.edit_message_caption(
        caption=query.message.caption + "\n\n❌ נדחה על ידי " + query.from_user.first_name
    )
    
    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text="הבקשה שלך נדחתה."
        )
    except Exception:
        pass


async def admin_help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback for admin help button."""
    query = update.callback_query
    await query.answer()
    
    from handlers.utils import is_super_admin
    user_id = query.from_user.id
    
    help_text = """
📋 פקודות אדמין זמינות:

/approve <user_id> - אישור משתמש חדש
/ban <user_id> - חסימת משתמש בכל הקבוצות
/lock - נעילת הקבוצה (קריאה בלבד)
/unlock - פתיחת הקבוצה
/pending - רשימת משתמשים ממתינים
"""
    
    if is_super_admin(user_id):
        help_text += """
👑 פקודות מנהל ראשי:
/addadmin <user_id> - הוספת מנהל
/removeadmin <user_id> - הסרת מנהל
/listadmins - רשימת מנהלים
/testadmin - בדיקת ערוץ ניהול
"""
    
    await query.edit_message_text(help_text, reply_markup=build_back_button())


async def pending_users_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback for pending users button."""
    query = update.callback_query
    await query.answer()
    
    from db_operations import get_all_pending_users
    pending = get_all_pending_users()
    
    if not pending:
        await query.edit_message_text("אין משתמשים ממתינים לאישור.", reply_markup=build_back_button())
        return
    
    text = "📝 משתמשים ממתינים לאישור:\n\n"
    for u in pending[:10]:
        text += f"• {u.full_name or 'ללא שם'} (ID: {u.telegram_id})\n"
        text += f"  טלפון: {u.phone_number or 'לא צוין'}\n\n"
    
    await query.edit_message_text(text, reply_markup=build_back_button())


async def test_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback for test admin channel button."""
    query = update.callback_query
    await query.answer()
    
    if not ADMIN_CHAT_ID:
        await query.edit_message_text("❌ ADMIN_CHAT_ID לא מוגדר!", reply_markup=build_back_button())
        return
    
    try:
        await context.bot.send_message(
            chat_id=int(ADMIN_CHAT_ID),
            text="✅ הודעת בדיקה מהבוט!\n\nערוץ הניהול מוגדר ועובד כראוי."
        )
        await query.edit_message_text(f"✅ הודעה נשלחה בהצלחה לערוץ הניהול!", reply_markup=build_back_button())
    except Exception as e:
        await query.edit_message_text(f"❌ שגיאה בשליחה:\n{e}", reply_markup=build_back_button())


async def create_sell_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback for create sell post button."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "כדי ליצור פוסט מכירה, שלח /sell ואחריו את תוכן הפוסט.\n\nלדוגמה:\n/sell מכירת רכב טויוטה 2020",
        reply_markup=build_back_button()
    )


async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback for returning to main menu."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    await query.edit_message_text(
        get_menu_text(user_id),
        reply_markup=build_main_menu(user_id)
    )


async def list_admins_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback for listing all admins."""
    query = update.callback_query
    await query.answer()
    
    from db_operations import get_all_admins
    admins = get_all_admins()
    
    if not admins:
        await query.edit_message_text("אין מנהלים במערכת.", reply_markup=build_back_button())
        return
    
    text = "👥 רשימת מנהלים:\n\n"
    for admin in admins:
        text += f"• {admin.full_name or 'ללא שם'} (ID: {admin.telegram_id})\n"
    
    await query.edit_message_text(text, reply_markup=build_back_button())


DAY_NAMES = {0: "ראשון", 1: "שני", 2: "שלישי", 3: "רביעי", 4: "חמישי", 5: "שישי"}


async def pending_posts_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback for viewing pending sell posts."""
    query = update.callback_query
    await query.answer()
    
    from db_operations import get_pending_sell_posts
    posts = get_pending_sell_posts()
    
    if not posts:
        await query.edit_message_text("אין מודעות ממתינות לאישור.", reply_markup=build_back_button())
        return
    
    await query.edit_message_text(f"📦 מודעות ממתינות ({len(posts)}):", reply_markup=build_back_button())
    
    for post in posts:
        user = get_user(post.user_id)
        day_name = DAY_NAMES.get(post.publication_day, "לא נבחר")
        keyboard = [
            [
                InlineKeyboardButton("✅ אשר", callback_data=f"approve_post_{post.id}"),
                InlineKeyboardButton("❌ דחה", callback_data=f"reject_post_{post.id}")
            ],
            [InlineKeyboardButton("🏠 חזרה לתפריט", callback_data="main_menu")]
        ]
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"📦 מודעה #{post.id}\n👤 מפרסם: {user.full_name if user else 'לא ידוע'}\n📅 יום פרסום: {day_name}\n\n{post.content}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def send_pending_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback for send all pending items to admin channel."""
    query = update.callback_query
    await query.answer("שולח ממתינים לערוץ...")
    
    from db_operations import get_all_pending_users, get_pending_sell_posts
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    
    pending_users = get_all_pending_users()
    pending_posts = get_pending_sell_posts()
    
    if not pending_users and not pending_posts:
        await query.edit_message_text("אין פריטים ממתינים במערכת.", reply_markup=build_back_button())
        return
    
    sent_count = 0
    
    for user in pending_users:
        try:
            message = f"""🔔 משתמש ממתין לאישור:

👤 שם: {user.full_name or 'לא צוין'}
📱 טלפון: {user.phone_number or 'לא צוין'}
🆔 Telegram ID: {user.telegram_id}"""
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ אשר", callback_data=f"approve_{user.telegram_id}"),
                    InlineKeyboardButton("❌ דחה", callback_data=f"ban_{user.telegram_id}")
                ]
            ]
            
            if user.license_photo_id:
                await context.bot.send_photo(
                    chat_id=int(ADMIN_CHAT_ID),
                    photo=user.license_photo_id,
                    caption=message,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                await context.bot.send_message(
                    chat_id=int(ADMIN_CHAT_ID),
                    text=message,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            sent_count += 1
        except Exception as e:
            logger.error(f"Failed to send pending user {user.telegram_id}: {e}")
    
    for post in pending_posts:
        try:
            user = get_user(post.user_id)
            message = f"""📦 מודעת מכירה ממתינה:

👤 מפרסם: {user.full_name if user else 'לא ידוע'}
🆔 ID: {post.user_id}

📝 תוכן:
{post.content}"""
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ אשר", callback_data=f"approve_post_{post.id}"),
                    InlineKeyboardButton("❌ דחה", callback_data=f"reject_post_{post.id}")
                ]
            ]
            
            await context.bot.send_message(
                chat_id=int(ADMIN_CHAT_ID),
                text=message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            sent_count += 1
        except Exception as e:
            logger.error(f"Failed to send pending post {post.id}: {e}")
    
    await query.edit_message_text(f"✅ נשלחו {sent_count} פריטים ממתינים לערוץ הניהול.", reply_markup=build_back_button())


def setup_verification_flow(application: Application):
    """Sets up the verification conversation handler."""
    from telegram.ext import CommandHandler
    
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start_verification),
            CommandHandler("verify", start_verification),
            CallbackQueryHandler(start_verify_callback, pattern="^start_verify$"),
        ],
        states={
            AWAITING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
            AWAITING_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_phone)],
            AWAITING_LICENSE: [MessageHandler(filters.PHOTO, receive_license)],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^ביטול$"), cancel_verification),
            CommandHandler("cancel", cancel_verification),
            CallbackQueryHandler(cancel_verify_callback, pattern="^cancel_verify$"),
        ],
        allow_reentry=True,
        per_chat=True,
        per_user=True
    )
    
    application.add_handler(conv_handler)
    
    application.add_handler(CallbackQueryHandler(main_menu_callback, pattern="^main_menu$"))
    application.add_handler(CallbackQueryHandler(list_admins_callback, pattern="^list_admins$"))
    application.add_handler(CallbackQueryHandler(pending_posts_callback, pattern="^pending_posts$"))
    application.add_handler(CallbackQueryHandler(approve_user_callback, pattern="^approve_"))
    application.add_handler(CallbackQueryHandler(ban_user_callback, pattern="^ban_"))
    application.add_handler(CallbackQueryHandler(admin_help_callback, pattern="^admin_help$"))
    application.add_handler(CallbackQueryHandler(pending_users_callback, pattern="^pending_users$"))
    application.add_handler(CallbackQueryHandler(test_admin_callback, pattern="^test_admin$"))
    application.add_handler(CallbackQueryHandler(create_sell_callback, pattern="^create_sell$"))
    application.add_handler(CallbackQueryHandler(send_pending_callback, pattern="^send_pending$"))
    
    logger.info("Verification flow setup complete")
