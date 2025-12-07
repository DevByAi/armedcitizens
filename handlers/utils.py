import os
import logging
from telegram import Bot, Chat, ChatMember, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatMemberStatus
from db_operations import get_user, ban_user_in_db
from typing import List
from enum import Enum


class UserRole(Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    APPROVED_USER = "approved_user"
    PENDING_USER = "pending_user"

DAY_NAMES = {0: "ראשון", 1: "שני", 2: "שלישי", 3: "רביעי", 4: "חמישי", 5: "שישי"}

logger = logging.getLogger(__name__)

# קבלת רשימת ה-IDs של הקבוצות מהסביבה
ALL_COMMUNITY_CHATS = [int(i) for i in os.getenv("ALL_COMMUNITY_CHATS", "").split(',') if i]

# ערוץ הניהול לקבלת בקשות אימות
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "")

# מנהל ראשי של המערכת
SUPER_ADMIN_ID = os.getenv("SUPER_ADMIN_ID", "")

def is_super_admin(user_id: int) -> bool:
    """Check if user is the super admin."""
    if not SUPER_ADMIN_ID:
        return False
    return str(user_id) == SUPER_ADMIN_ID

async def restrict_user_permissions(chat_id: int, user_id: int, can_write: bool = False):
    permissions = ChatPermissions(can_send_messages=can_write)
    try:
        await Bot(os.getenv("BOT_TOKEN")).restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=permissions,
        )
        return True
    except Exception as e:
        logger.warning(f"Failed to set permissions for user {user_id} in {chat_id}: {e}")
        return False

async def grant_user_permissions(chat_id: int, user_id: int):
    return await restrict_user_permissions(chat_id, user_id, can_write=True)

async def is_user_approved(telegram_id: int) -> bool:
    user = get_user(telegram_id)
    return user is not None and user.is_approved and not user.is_banned

async def is_chat_admin(chat: Chat, user) -> bool:
    """Check if user is an admin (super admin, DB admin, or Telegram group admin)."""
    if hasattr(user, 'is_bot') and user.is_bot:
        return False
    
    user_id = user.id if hasattr(user, 'id') else user
    
    # Check if super admin
    if is_super_admin(user_id):
        return True
    
    # Check if admin in database
    db_user = get_user(user_id)
    if db_user and db_user.is_admin:
        return True
    
    # Check if Telegram group admin
    try:
        member = await chat.get_member(user_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except Exception:
        return False

async def ban_user_globally(bot: Bot, target_user_id: int) -> bool:
    ban_user_in_db(target_user_id)
    success_count = 0
    for chat_id in ALL_COMMUNITY_CHATS:
        try:
            await bot.ban_chat_member(chat_id, target_user_id)
            success_count += 1
        except Exception:
            pass 
    return success_count > 0

async def set_group_read_only(bot: Bot, chat_id: int, is_read_only: bool) -> bool:
    permissions = ChatPermissions(can_send_messages=not is_read_only)
    try:
        await bot.set_chat_permissions(chat_id, permissions)
        return True
    except Exception as e:
        logger.error(f"Failed to set group permissions for chat {chat_id}: {e}")
        return False


def get_user_role(user_id: int) -> UserRole:
    """Determine user's role based on their status."""
    if is_super_admin(user_id):
        return UserRole.SUPER_ADMIN
    
    user = get_user(user_id)
    if user:
        if user.is_admin:
            return UserRole.ADMIN
        if user.is_approved and not user.is_banned:
            return UserRole.APPROVED_USER
    
    return UserRole.PENDING_USER


def build_main_menu(user_id: int) -> InlineKeyboardMarkup:
    """Build role-appropriate main menu keyboard."""
    role = get_user_role(user_id)
    keyboard = []
    
    if role == UserRole.SUPER_ADMIN:
        keyboard = [
            [InlineKeyboardButton("📋 פקודות אדמין", callback_data="admin_help")],
            [InlineKeyboardButton("📝 משתמשים ממתינים", callback_data="pending_users")],
            [InlineKeyboardButton("📦 מודעות ממתינות", callback_data="pending_posts")],
            [InlineKeyboardButton("📤 שלח ממתינים לערוץ", callback_data="send_pending")],
            [InlineKeyboardButton("👥 רשימת מנהלים", callback_data="list_admins")],
            [InlineKeyboardButton("🧪 בדיקת ערוץ ניהול", callback_data="test_admin")]
        ]
    elif role == UserRole.ADMIN:
        keyboard = [
            [InlineKeyboardButton("📋 פקודות אדמין", callback_data="admin_help")],
            [InlineKeyboardButton("📝 משתמשים ממתינים", callback_data="pending_users")],
            [InlineKeyboardButton("📦 מודעות ממתינות", callback_data="pending_posts")],
            [InlineKeyboardButton("📤 שלח ממתינים לערוץ", callback_data="send_pending")]
        ]
    elif role == UserRole.APPROVED_USER:
        keyboard = [
            [InlineKeyboardButton("📦 יצירת פוסט מכירה", callback_data="create_sell")],
            [InlineKeyboardButton("📋 המודעות שלי", callback_data="my_posts")]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("✅ התחל אימות", callback_data="start_verify")]
        ]
    
    return InlineKeyboardMarkup(keyboard)


def build_back_button() -> InlineKeyboardMarkup:
    """Build a simple back to menu button."""
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 חזרה לתפריט", callback_data="main_menu")]])


def add_back_button(keyboard_list: list) -> list:
    """Add back to menu button to existing keyboard list."""
    keyboard_list.append([InlineKeyboardButton("🏠 חזרה לתפריט", callback_data="main_menu")])
    return keyboard_list


def get_menu_text(user_id: int) -> str:
    """Get appropriate menu text based on user role."""
    role = get_user_role(user_id)
    
    if role == UserRole.SUPER_ADMIN:
        return "שלום מנהל ראשי! בחר פעולה:"
    elif role == UserRole.ADMIN:
        return "שלום מנהל! בחר פעולה:"
    elif role == UserRole.APPROVED_USER:
        return "שלום! בחר פעולה:"
    else:
        return "ברוך הבא! כדי לקבל גישה לקהילה, עליך לעבור תהליך אימות."

