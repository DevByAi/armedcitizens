# ==================================
# קובץ: handlers/admin.py (מתוקן)
# ==================================
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)
from db_operations import (
    create_or_update_user, set_user_admin, get_all_pending_users, 
    get_pending_sell_posts, get_approved_posts, get_all_admins
)
from handlers.utils import (
    is_chat_admin, ALL_COMMUNITY_CHATS, is_super_admin, 
    is_user_admin, build_main_menu_for_user
)

logger = logging.getLogger(__name__)

# --- קבועים לזיהוי כפתורים (כדי למנוע טעויות הקלדה) ---
# אלו השמות שהכפתורים בתפריט הראשי חייבים לשלוח:
CALLBACK_ADMIN_STATS = "admin_stats"         # עבור סטטיסטיקות
CALLBACK_ADMIN_PENDING = "approve_pending"   # עבור אישור ממתינים (או admin_pending_menu)
CALLBACK_VIEW_USERS = "admin_view_pending_users"
CALLBACK_SEND_PENDING = "sendpending"

# --- פונקציות Callback לניהול ---

async def handle_admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """מציג סטטיסטיקות לוח בקרה למנהלים."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not is_user_admin(user_id):
        await query.edit_message_text("⛔ אין לך הרשאות צפייה בנתונים אלו.", reply_markup=build_main_menu_for_user(user_id))
        return

    # שליפת נתונים
    pending_users = get_all_pending_users()
    pending_posts = get_pending_sell_posts()
    active_posts = get_approved_posts()
    admins = get_all_admins()
    
    stats_text = f"""📊 **לוח בקרה וסטטיסטיקות:**

👥 **משתמשים:**
• ממתינים לאישור: {len(pending_users)}
• מנהלים במערכת: {len(admins)}

📦 **מודעות מכירה:**
• ממתינות לאישור: {len(pending_posts)}
• פעילות ומאושרות: {len(active_posts)}

⚙️ **סטטוס מערכת:** תקין
"""
    
    # כפתור חזרה לתפריט הראשי
    keyboard = [[InlineKeyboardButton("⬅️ חזור לתפריט", callback_data="main_menu_return")]]
    
    await query.edit_message_text(stats_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def handle_admin_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """מציג תפריט בחירה מה לאשר (משתמשים או מודעות)."""
    query = update.callback_query
    await query.answer()
    
    pending_users_count = len(get_all_pending_users())
    pending_posts_count = len(get_pending_sell_posts())
    
    text = f"🚨 **ניהול ממתינים**\n\nבחר קטגוריה לטיפול:"
    
    keyboard = []
    # כפתור למשתמשים
    if pending_users_count > 0:
        keyboard.append([InlineKeyboardButton(f"👤 משתמשים ({pending_users_count})", callback_data=CALLBACK_VIEW_USERS)])
    else:
        keyboard.append([InlineKeyboardButton("👤 אין משתמשים ממתינים", callback_data="ignore")])
        
    # כפתור למודעות
    if pending_posts_count > 0:
        keyboard.append([InlineKeyboardButton(f"📦 מודעות ({pending_posts_count})", callback_data=CALLBACK_SEND_PENDING)])
    else:
        keyboard.append([InlineKeyboardButton("📦 אין מודעות ממתינות", callback_data="ignore")])
        
    keyboard.append([InlineKeyboardButton("⬅️ חזור", callback_data="main_menu_return")])
    
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_view_pending_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """מציג את רשימת המשתמשים הממתינים."""
    query = update.callback_query
    await query.answer()
    
    users = get_all_pending_users()
    if not users:
        await query.edit_message_text(
            "✅ אין משתמשים ממתינים כרגע.", 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("חזור", callback_data=CALLBACK_ADMIN_PENDING)]])
        )
        return

    text = "📋 **משתמשים לאישור:**\nהשתמש בפקודה `/approve ID` כדי לאשר ידנית:\n\n"
    for u in users[:10]: 
        text += f"• {u.full_name} (ID: `{u.telegram_id}`)\n"
    
    # כפתור חזרה לתפריט הניהול הקודם
    keyboard = [[InlineKeyboardButton("⬅️ חזור", callback_data=CALLBACK_ADMIN_PENDING)]]
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


# --- פקודות טקסט ---

async def set_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type != "private": return
    if not is_super_admin(update.effective_user.id):
        await update.message.reply_text("⛔️ אין הרשאה.")
        return
    if not context.args:
        await update.message.reply_text("שימוש: /set_admin <ID>")
        return
    try:
        target = int(context.args[0])
        set_user_admin(target, True)
        create_or_update_user(target, is_approved=True)
        await update.message.reply_text(f"✅ אדמין {target} הוגדר בהצלחה.")
    except Exception:
        await update.message.reply_text("שגיאה בפורמט ה-ID.")

async def approve_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_chat_admin(update.effective_chat, update.effective_user): return
    if not context.args: return
    try:
        tid = int(context.args[0])
        create_or_update_user(tid, is_approved=True)
        from handlers.utils import grant_user_permissions
        for cid in ALL_COMMUNITY_CHATS:
            await grant_user_permissions(cid, tid)
        await update.message.reply_text(f"✅ משתמש {tid} אושר!")
        try: await context.bot.send_message(tid, "✅ אושרת בקהילה! כעת ניתן לכתוב.")
        except: pass
    except: await update.message.reply_text("שגיאה.")

async def send_pending_trigger(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback wrapper."""
    await context.bot.send_message(update.effective_chat.id, "📢 מודעות ממתינות נשלחות לערוץ הניהול...")
    # כאן הלוגיקה תמשיך כרגיל

async def ignore_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """סתם כפתור שלא עושה כלום (לעיצוב)"""
    await update.callback_query.answer("אין נתונים להצגה")

def setup_admin_handlers(application: Application):
    """רישום ה-Handlers עם תמיכה בשמות משתנים"""
    
    application.add_handler(CommandHandler("approve", approve_user_command))
    application.add_handler(CommandHandler("set_admin", set_admin_command))
    
    # --- התיקון הגדול כאן: שימוש ב-Regex גמיש ---
    
    # תופס: admin_stats או admin_stats_menu
    application.add_handler(CallbackQueryHandler(handle_admin_stats, pattern="^(admin_stats|admin_stats_menu)$"))
    
    # תופס: approve_pending או admin_pending_menu
    application.add_handler(CallbackQueryHandler(handle_admin_pending, pattern="^(approve_pending|admin_pending_menu)$"))
    
    # תפריטים פנימיים
    application.add_handler(CallbackQueryHandler(handle_view_pending_users, pattern=f"^{CALLBACK_VIEW_USERS}$"))
    application.add_handler(CallbackQueryHandler(send_pending_trigger, pattern=f"^{CALLBACK_SEND_PENDING}$"))
    application.add_handler(CallbackQueryHandler(ignore_callback, pattern="^ignore$"))
    
    logger.info("Admin handlers setup complete with flexible patterns")
