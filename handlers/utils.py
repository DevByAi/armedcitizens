# ==================================
# קובץ: handlers/utils.py (מלא וסופי)
# ==================================
import os
import logging
from telegram import Bot, ChatPermissions, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from typing import List

from db_operations import get_user, ban_user_in_db

logger = logging.getLogger(__name__)

# --- משתני סביבה גלובליים (חובה להגדרה ב-Render) ---
SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", 0))
ADMIN_CHAT_ID = os.getenv("ADMIN_CHANNEL_ID") 
SELL_GROUP_ID = os.getenv("SELL_GROUP_ID") 
ALL_COMMUNITY_CHATS = []
if os.getenv("ALL_COMMUNITY_CHATS"):
    try:
        ALL_COMMUNITY_CHATS = [int(cid.strip()) for cid in os.getenv("ALL_COMMUNITY_CHATS").split(',') if cid.strip()]
    except ValueError:
        logger.error("ALL_COMMUNITY_CHATS must contain comma-separated integer IDs.")

# --- קבועים ---
DAY_NAMES = {
    0: "ראשון", 1: "שני", 2: "שלישי", 3: "רביעי", 4: "חמישי", 5: "שישי"
}


# --- בדיקות הרשאה ---
def is_super_admin(user_id: int) -> bool:
    """מחזיר True אם המשתמש הוא הסופר-אדמין."""
    return user_id == SUPER_ADMIN_ID

async def is_chat_admin(chat: Update.effective_chat, user: Update.effective_user) -> bool:
    """בדיקה אם המשתמש הוא אדמין בצ'אט הנתון (כולל אדמין DB)."""
    user_db = get_user(user.id)
    if user_db and user_db.is_admin:
        return True
    
    try:
        member = await chat.get_member(user.id)
        if member.status in ('administrator', 'creator'):
            return True
    except Exception:
        pass
    
    return is_super_admin(user.id)

# --- פעולות על הרשאות ---
async def restrict_user_permissions(chat_id: int, user_id: int):
    """מגביל משתמש להודעות טקסט בלבד ומונע מדיה."""
    permissions = ChatPermissions(
        can_send_messages=False,
        can_send_media_messages=False,
        can_send_polls=False,
        can_send_other_messages=False,
        can_add_web_page_previews=False,
        can_change_info=False,
        can_invite_users=False,
        can_pin_messages=False
    )
    await Bot(os.getenv("BOT_TOKEN")).restrict_chat_member(chat_id, user_id, permissions)

async def grant_user_permissions(chat_id: int, user_id: int):
    """נותן למשתמש הרשאות כתיבה מלאות."""
    permissions = ChatPermissions(
        can_send_messages=True,
        can_send_media_messages=True,
        can_send_polls=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
        can_change_info=False,
        can_invite_users=True,
        can_pin_messages=False
    )
    await Bot(os.getenv("BOT_TOKEN")).restrict_chat_member(chat_id, user_id, permissions)

async def ban_user_globally(bot: Bot, user_id: int) -> bool:
    """חוסם משתמש מכל קבוצות הקהילה ומעדכן DB."""
    success = True
    
    for chat_id in ALL_COMMUNITY_CHATS:
        try:
            await bot.ban_chat_member(chat_id, user_id)
        except Exception as e:
            logger.error(f"Failed to ban user {user_id} from chat {chat_id}: {e}")
            success = False
            
    ban_user_in_db(user_id)
    
    return success

async def set_group_read_only(bot: Bot, chat_id: int, is_read_only: bool) -> bool:
    """הופך קבוצה למצב קריאה בלבד או מחזיר הרשאות כתיבה."""
    if is_read_only:
        permissions = ChatPermissions(can_send_messages=False)
    else:
        permissions = ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True
        )
        
    try:
        await bot.set_chat_permissions(chat_id, permissions)
        return True
    except Exception as e:
        logger.error(f"Failed to {'lock' if is_read_only else 'unlock'} chat {chat_id}: {e}")
        return False

# --- פונקציות לתמיכה במקלדת ---
async def check_user_status_and_reply(message: Update.message, context: ContextTypes.DEFAULT_TYPE):
    """בדיקת סטטוס אימות ושליחת תגובה מתאימה (עבור המקלדת הצפה)."""
    user_id = message.chat_id
    user = get_user(user_id)
    
    if not user:
        status_text = "❌ עדיין לא התחלת את תהליך האימות. אנא המתן עד שתשלח הודעה ראשונה לאחת מקבוצות הקהילה."
    elif user.is_banned:
        status_text = "🚫 המשתמש חסום. אין אפשרות להצטרף."
    elif user.is_approved:
        status_text = "✅ אושר! יש לך הרשאות כתיבה מלאות."
    else:
        status_text = "⏳ ממתין לאישור מנהל. פרטיך נשלחו לבדיקה."
        
    await message.reply_text(status_text)
    
def build_back_button():
    """בונה כפתור חזור בסיסי למקלדות משניות."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("חזור לתפריט הראשי", callback_data="main_menu_return")]
    ])

def build_main_menu():
    """בונה את המקלדת הצפה הראשית."""
    keyboard = [
        [InlineKeyboardButton("📦 מכירה חדשה", callback_data="start_sell_flow")],
        [InlineKeyboardButton("👤 מצב אימות", callback_data="check_verification_status")],
        [InlineKeyboardButton("❓ עזרה ופקודות", callback_data="help_menu_main")]
    ]
    return InlineKeyboardMarkup(keyboard)
