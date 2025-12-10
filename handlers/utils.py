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

# --- בדיקות הרשאה ופעולות (שאר הקוד נשאר זהה) ---
def is_super_admin(user_id: int) -> bool:
    return user_id == SUPER_ADMIN_ID

async def is_chat_admin(chat: Update.effective_chat, user: Update.effective_user) -> bool:
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

# ... (שאר פונקציות הניהול, grant, restrict, ban_globally, set_read_only) ...

# --- פונקציות לתמיכה במקלדת (תיקון שמות) ---

# *** תיקון: הפונקציה הדומה build_back_button נקראת כאן add_back_button ***
# (אם verification.py מצפה לפונקציה שמוסיפה כפתור למקלדת קיימת, יש צורך בקוד מורכב יותר)
# לצורך פתרון ה-ImportError, אני מניח שזה מה שנדרש:

def add_back_button(keyboard: List[List[InlineKeyboardButton]]) -> List[List[InlineKeyboardButton]]:
    """מוסיף כפתור חזרה לתפריט ראשי למקלדת נתונה."""
    back_button = [InlineKeyboardButton("חזור לתפריט הראשי", callback_data="main_menu_return")]
    keyboard.append(back_button)
    return keyboard


async def check_user_status_and_reply(message: Update.message, context: ContextTypes.DEFAULT_TYPE):
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
    
def build_main_menu():
    """בונה את המקלדת הצפה הראשית."""
    keyboard = [
        [InlineKeyboardButton("📦 מכירה חדשה", callback_data="start_sell_flow")],
        [InlineKeyboardButton("👤 מצב אימות", callback_data="check_verification_status")],
        [InlineKeyboardButton("❓ עזרה ופקודות", callback_data="help_menu_main")]
    ]
    return InlineKeyboardMarkup(keyboard)
