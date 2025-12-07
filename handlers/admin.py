import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)
from db_operations import get_user, create_or_update_user, ban_user_in_db, get_all_admins, set_user_admin, get_all_pending_users
from handlers.utils import ban_user_globally, set_group_read_only, is_chat_admin, ALL_COMMUNITY_CHATS, is_super_admin, SUPER_ADMIN_ID, build_back_button

logger = logging.getLogger(__name__)


async def approve_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to approve a user: /approve <user_id>"""
    if not await is_chat_admin(update.effective_chat, update.effective_user):
        await update.message.reply_text("אין לך הרשאות אדמין.")
        return
    
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("שימוש: /approve <user_id>")
        return
    
    try:
        target_user_id = int(context.args[0])
        user = get_user(target_user_id)
        
        if not user:
            await update.message.reply_text("משתמש לא נמצא במערכת.")
            return
        
        # Approve the user
        create_or_update_user(target_user_id, is_approved=True)
        
        # Grant permissions in all community chats
        from handlers.utils import grant_user_permissions
        for chat_id in ALL_COMMUNITY_CHATS:
            try:
                await grant_user_permissions(chat_id, target_user_id)
            except Exception as e:
                logger.warning(f"Could not grant permissions in chat {chat_id}: {e}")
        
        await update.message.reply_text(f"המשתמש {target_user_id} אושר בהצלחה!")
        
        # Notify the user
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text="הבקשה שלך לאישור אושרה! כעת יש לך גישה לכל קבוצות הקהילה."
            )
        except Exception:
            pass
            
    except ValueError:
        await update.message.reply_text("מזהה משתמש לא חוקי.")
    except Exception as e:
        logger.error(f"Error approving user: {e}")
        await update.message.reply_text("שגיאה באישור המשתמש.")


async def ban_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to ban a user globally: /ban <user_id>"""
    if not await is_chat_admin(update.effective_chat, update.effective_user):
        await update.message.reply_text("אין לך הרשאות אדמין.")
        return
    
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("שימוש: /ban <user_id>")
        return
    
    try:
        target_user_id = int(context.args[0])
        
        # Ban globally
        success = await ban_user_globally(context.bot, target_user_id)
        
        if success:
            await update.message.reply_text(f"המשתמש {target_user_id} נחסם בכל הקבוצות.")
        else:
            await update.message.reply_text("שגיאה בחסימת המשתמש.")
            
    except ValueError:
        await update.message.reply_text("מזהה משתמש לא חוקי.")
    except Exception as e:
        logger.error(f"Error banning user: {e}")
        await update.message.reply_text("שגיאה בחסימת המשתמש.")


async def lock_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to lock a group (make it read-only): /lock"""
    if not await is_chat_admin(update.effective_chat, update.effective_user):
        await update.message.reply_text("אין לך הרשאות אדמין.")
        return
    
    chat_id = update.effective_chat.id
    success = await set_group_read_only(context.bot, chat_id, is_read_only=True)
    
    if success:
        await update.message.reply_text("הקבוצה ננעלה. רק אדמינים יכולים לכתוב.")
    else:
        await update.message.reply_text("שגיאה בנעילת הקבוצה.")


async def unlock_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to unlock a group: /unlock"""
    if not await is_chat_admin(update.effective_chat, update.effective_user):
        await update.message.reply_text("אין לך הרשאות אדמין.")
        return
    
    chat_id = update.effective_chat.id
    success = await set_group_read_only(context.bot, chat_id, is_read_only=False)
    
    if success:
        await update.message.reply_text("הקבוצה נפתחה. כולם יכולים לכתוב.")
    else:
        await update.message.reply_text("שגיאה בפתיחת הקבוצה.")


async def admin_help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows admin commands help."""
    user_id = update.effective_user.id
    logger.info(f"adminhelp called by user_id={user_id}, SUPER_ADMIN_ID={SUPER_ADMIN_ID}, is_super={is_super_admin(user_id)}")
    user = get_user(user_id)
    is_admin = (user and user.is_admin) or is_super_admin(user_id)
    
    if not is_admin:
        await update.message.reply_text(f"אין לך הרשאות. ה-ID שלך: {user_id}")
        return
    
    help_text = """
פקודות אדמין זמינות:

/approve <user_id> - אישור משתמש חדש
/ban <user_id> - חסימת משתמש בכל הקבוצות
/lock - נעילת הקבוצה (קריאה בלבד)
/unlock - פתיחת הקבוצה (כולם יכולים לכתוב)
/pending - רשימת משתמשים ממתינים לאישור
/adminhelp - הצגת הודעת עזרה זו
"""
    
    if is_super_admin(user_id):
        help_text += """
פקודות מנהל ראשי:
/addadmin <user_id> - הוספת מנהל לצוות
/removeadmin <user_id> - הסרת מנהל מהצוות
/listadmins - רשימת כל המנהלים
"""
    
    await update.message.reply_text(help_text)


async def add_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Super admin command to add a team member: /addadmin <user_id>"""
    if not is_super_admin(update.effective_user.id):
        await update.message.reply_text("רק המנהל הראשי יכול להוסיף מנהלים.")
        return
    
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("שימוש: /addadmin <user_id>")
        return
    
    try:
        target_user_id = int(context.args[0])
        set_user_admin(target_user_id, True)
        await update.message.reply_text(f"המשתמש {target_user_id} נוסף כמנהל בצוות!")
    except ValueError:
        await update.message.reply_text("מזהה משתמש לא חוקי.")


async def remove_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Super admin command to remove a team member: /removeadmin <user_id>"""
    if not is_super_admin(update.effective_user.id):
        await update.message.reply_text("רק המנהל הראשי יכול להסיר מנהלים.")
        return
    
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("שימוש: /removeadmin <user_id>")
        return
    
    try:
        target_user_id = int(context.args[0])
        set_user_admin(target_user_id, False)
        await update.message.reply_text(f"המשתמש {target_user_id} הוסר מהצוות.")
    except ValueError:
        await update.message.reply_text("מזהה משתמש לא חוקי.")


async def list_admins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Super admin command to list all admins: /listadmins"""
    if not is_super_admin(update.effective_user.id):
        await update.message.reply_text("רק המנהל הראשי יכול לראות את רשימת המנהלים.")
        return
    
    admins = get_all_admins()
    
    if not admins:
        text = f"אין מנהלים נוספים.\n\nמנהל ראשי: {SUPER_ADMIN_ID}"
    else:
        admin_list = "\n".join([f"- {a.telegram_id} ({a.full_name or 'ללא שם'})" for a in admins])
        text = f"מנהל ראשי: {SUPER_ADMIN_ID}\n\nמנהלי צוות:\n{admin_list}"
    
    await update.message.reply_text(text)


async def test_admin_channel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Super admin command to test admin channel: /testadmin"""
    from handlers.utils import ADMIN_CHAT_ID
    
    if not is_super_admin(update.effective_user.id):
        await update.message.reply_text("רק המנהל הראשי יכול לבדוק את ערוץ הניהול.")
        return
    
    if not ADMIN_CHAT_ID:
        await update.message.reply_text("❌ ADMIN_CHAT_ID לא מוגדר!\n\nהגדר את המשתנה בהגדרות הסביבה.")
        return
    
    try:
        await context.bot.send_message(
            chat_id=int(ADMIN_CHAT_ID),
            text="✅ הודעת בדיקה מהבוט!\n\nערוץ הניהול מוגדר ועובד כראוי."
        )
        await update.message.reply_text(f"✅ הודעה נשלחה בהצלחה לערוץ {ADMIN_CHAT_ID}")
    except Exception as e:
        await update.message.reply_text(f"❌ שגיאה בשליחה לערוץ {ADMIN_CHAT_ID}:\n{e}")


async def send_all_pending_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Super admin command to send all pending items to admin channel: /sendpending"""
    from handlers.utils import ADMIN_CHAT_ID
    from db_operations import get_pending_sell_posts
    
    if not is_super_admin(update.effective_user.id):
        await update.message.reply_text("רק המנהל הראשי יכול לשלוח את כל הממתינים.")
        return
    
    if not ADMIN_CHAT_ID:
        await update.message.reply_text("❌ ADMIN_CHAT_ID לא מוגדר!")
        return
    
    pending_users = get_all_pending_users()
    pending_posts = get_pending_sell_posts()
    
    if not pending_users and not pending_posts:
        await update.message.reply_text("אין פריטים ממתינים במערכת.")
        return
    
    sent_count = 0
    
    for user in pending_users:
        try:
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
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
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
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
    
    await update.message.reply_text(f"✅ נשלחו {sent_count} פריטים ממתינים לערוץ הניהול.")


async def pending_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show list of users pending approval: /pending"""
    user_id = update.effective_user.id
    user = get_user(user_id)
    is_admin = (user and user.is_admin) or is_super_admin(user_id)
    
    if not is_admin:
        await update.message.reply_text("אין לך הרשאות.")
        return
    
    pending = get_all_pending_users()
    
    if not pending:
        await update.message.reply_text("אין משתמשים ממתינים לאישור.")
        return
    
    text = "משתמשים ממתינים לאישור:\n\n"
    for u in pending[:20]:
        text += f"- {u.full_name or 'ללא שם'} (ID: {u.telegram_id})\n"
        text += f"  טלפון: {u.phone_number or 'לא צוין'}\n"
        text += f"  /approve {u.telegram_id}\n\n"
    
    await update.message.reply_text(text)


def setup_admin_handlers(application: Application):
    """Sets up all admin command handlers."""
    application.add_handler(CommandHandler("approve", approve_user_command))
    application.add_handler(CommandHandler("ban", ban_user_command))
    application.add_handler(CommandHandler("lock", lock_group_command))
    application.add_handler(CommandHandler("unlock", unlock_group_command))
    application.add_handler(CommandHandler("adminhelp", admin_help_command))
    application.add_handler(CommandHandler("addadmin", add_admin_command))
    application.add_handler(CommandHandler("removeadmin", remove_admin_command))
    application.add_handler(CommandHandler("listadmins", list_admins_command))
    application.add_handler(CommandHandler("pending", pending_users_command))
    application.add_handler(CommandHandler("testadmin", test_admin_channel_command))
    application.add_handler(CommandHandler("sendpending", send_all_pending_command))
    
    logger.info("Admin handlers setup complete")
