import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes
)
from db_operations import add_sell_post, get_approved_posts, get_user, set_post_publication_day, set_post_relevance, get_available_slots_for_day, set_post_time_slot
from handlers.utils import is_user_approved, ALL_COMMUNITY_CHATS, ADMIN_CHAT_ID, build_back_button

DAY_NAMES = {0: "ראשון", 1: "שני", 2: "שלישי", 3: "רביעי", 4: "חמישי", 5: "שישי"}

logger = logging.getLogger(__name__)

AWAITING_SELL_CONTENT = 0


async def new_sell_post_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Allows users to create a new selling post: /sell"""
    user_id = update.effective_user.id
    
    if not await is_user_approved(user_id):
        await update.message.reply_text("עליך להיות משתמש מאושר כדי לפרסם מודעות.")
        return ConversationHandler.END
    
    if context.args:
        content = ' '.join(context.args)
        return await save_sell_post(update, context, content)
    
    keyboard = [[InlineKeyboardButton("❌ ביטול", callback_data="cancel_sell")]]
    await update.message.reply_text(
        "שלח את תוכן המודעה שלך (טקסט, תמונה או וידאו).\n"
        "המודעה תישלח לאישור אדמין לפני שתפורסם.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return AWAITING_SELL_CONTENT


async def receive_sell_post_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives the content of a selling post."""
    content = update.message.text or update.message.caption or "תמונה/וידאו"
    return await save_sell_post(update, context, content)


async def save_sell_post(update: Update, context: ContextTypes.DEFAULT_TYPE, content: str):
    """Saves the sell post and asks for publication day."""
    user_id = update.effective_user.id
    
    post = add_sell_post(user_id=user_id, content=content)
    context.user_data['new_post_id'] = post.id
    
    keyboard = [
        [
            InlineKeyboardButton("ראשון", callback_data=f"set_day_{post.id}_0"),
            InlineKeyboardButton("שני", callback_data=f"set_day_{post.id}_1"),
            InlineKeyboardButton("שלישי", callback_data=f"set_day_{post.id}_2")
        ],
        [
            InlineKeyboardButton("רביעי", callback_data=f"set_day_{post.id}_3"),
            InlineKeyboardButton("חמישי", callback_data=f"set_day_{post.id}_4"),
            InlineKeyboardButton("שישי", callback_data=f"set_day_{post.id}_5")
        ]
    ]
    
    await update.message.reply_text(
        f"✅ המודעה שלך נשמרה (מזהה: {post.id}).\n\n"
        "באיזה יום בשבוע תרצה לפרסם את המודעה?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    logger.info(f"New sell post created by user {user_id}, post ID: {post.id}")
    return ConversationHandler.END


async def set_day_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback for setting publication day - then shows time slot selection."""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    post_id = int(parts[2])
    day = int(parts[3])
    
    set_post_publication_day(post_id, day)
    
    available_slots = get_available_slots_for_day(day)
    
    if not available_slots:
        await query.edit_message_text(
            f"אין שעות פנויות ביום {DAY_NAMES[day]}. בחר יום אחר:",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("ראשון", callback_data=f"set_day_{post_id}_0"),
                    InlineKeyboardButton("שני", callback_data=f"set_day_{post_id}_1"),
                    InlineKeyboardButton("שלישי", callback_data=f"set_day_{post_id}_2")
                ],
                [
                    InlineKeyboardButton("רביעי", callback_data=f"set_day_{post_id}_3"),
                    InlineKeyboardButton("חמישי", callback_data=f"set_day_{post_id}_4"),
                    InlineKeyboardButton("שישי", callback_data=f"set_day_{post_id}_5")
                ]
            ])
        )
        return
    
    keyboard = []
    row = []
    for slot in available_slots:
        row.append(InlineKeyboardButton(f"{slot}:00", callback_data=f"set_slot_{post_id}_{day}_{slot}"))
        if len(row) == 4:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    await query.edit_message_text(
        f"✅ בחרת יום {DAY_NAMES[day]}.\n\n"
        f"בחר שעה לפרסום ({len(available_slots)} שעות פנויות):",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def set_slot_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback for setting publication time slot."""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    post_id = int(parts[2])
    day = int(parts[3])
    slot = int(parts[4])
    
    set_post_time_slot(post_id, slot)
    
    from db_operations import get_sell_post
    post = get_sell_post(post_id)
    user_id = query.from_user.id
    username = query.from_user.username or "אין"
    
    await query.edit_message_text(
        f"✅ המודעה תפורסם ביום {DAY_NAMES[day]} בשעה {slot}:00!\n"
        "היא תישלח לאישור אדמין ותפורסם לאחר מכן.",
        reply_markup=build_back_button()
    )
    
    if ADMIN_CHAT_ID and post:
        try:
            user = get_user(user_id)
            available_slots = get_available_slots_for_day(day)
            slots_text = ", ".join([f"{s}:00" for s in available_slots if s != slot])
            
            admin_message = f"""📦 מודעת מכירה חדשה:

👤 מפרסם: {user.full_name if user else 'לא ידוע'} (@{username})
🆔 ID: {user_id}
📅 יום פרסום: {DAY_NAMES[day]}
⏰ שעה: {slot}:00

📝 תוכן:
{post.content}

🕐 שעות פנויות נוספות ביום זה: {slots_text or 'אין'}"""
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ אשר", callback_data=f"approve_post_{post_id}"),
                    InlineKeyboardButton("❌ דחה", callback_data=f"reject_post_{post_id}")
                ]
            ]
            
            await context.bot.send_message(
                chat_id=int(ADMIN_CHAT_ID),
                text=admin_message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Failed to send sell post to admin: {e}")


async def cancel_sell_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel sell post creation."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("יצירת המודעה בוטלה.", reply_markup=build_back_button())
    return ConversationHandler.END


async def approve_post_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin approves a sell post."""
    query = update.callback_query
    await query.answer()
    
    post_id = int(query.data.replace("approve_post_", ""))
    
    from db_operations import approve_sell_post
    post = approve_sell_post(post_id)
    
    if post:
        await query.edit_message_text(
            query.message.text + f"\n\n✅ אושר על ידי {query.from_user.first_name}"
        )
        
        try:
            await context.bot.send_message(
                chat_id=post.user_id,
                text="🎉 מודעת המכירה שלך אושרה ותפורסם בקרוב!"
            )
        except Exception:
            pass
    else:
        await query.edit_message_text(
            query.message.text + "\n\n❌ שגיאה באישור המודעה"
        )


async def reject_post_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin rejects a sell post."""
    query = update.callback_query
    await query.answer()
    
    post_id = int(query.data.replace("reject_post_", ""))
    
    from db_operations import reject_sell_post
    post = reject_sell_post(post_id)
    
    await query.edit_message_text(
        query.message.text + f"\n\n❌ נדחה על ידי {query.from_user.first_name}"
    )
    
    if post:
        try:
            await context.bot.send_message(
                chat_id=post.user_id,
                text="מודעת המכירה שלך נדחתה על ידי האדמין."
            )
        except Exception:
            pass


async def send_posts_and_ask_relevance(context: ContextTypes.DEFAULT_TYPE):
    """Weekly job to send approved posts to community chats."""
    try:
        posts = get_approved_posts()
        
        if not posts:
            logger.info("No approved posts to send")
            return
        
        for chat_id in ALL_COMMUNITY_CHATS:
            for post in posts:
                try:
                    keyboard = [
                        [
                            InlineKeyboardButton("רלוונטי ✅", callback_data=f"relevant_{post.id}"),
                            InlineKeyboardButton("לא רלוונטי ❌", callback_data=f"irrelevant_{post.id}")
                        ]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"מודעת מכירה:\n\n{post.content}",
                        reply_markup=reply_markup
                    )
                    
                    from db_models import get_db_session
                    with get_db_session() as db:
                        db_post = db.query(type(post)).filter_by(id=post.id).first()
                        if db_post:
                            db_post.last_sent_date = datetime.now()
                            db.commit()
                            
                except Exception as e:
                    logger.error(f"Error sending post {post.id} to chat {chat_id}: {e}")
        
        logger.info(f"Successfully sent {len(posts)} posts to community chats")
        
    except Exception as e:
        logger.error(f"Error in send_posts_and_ask_relevance: {e}")


async def handle_relevance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles relevance button callbacks from community posts."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data.startswith("relevant_") or data.startswith("irrelevant_"):
        await query.edit_message_reply_markup(reply_markup=None)


async def confirm_relevance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User confirms their post is still relevant this week."""
    query = update.callback_query
    await query.answer()
    
    post_id = int(query.data.replace("confirm_relevant_", ""))
    
    set_post_relevance(post_id, True)
    
    await query.edit_message_text(
        "✅ המודעה שלך סומנה כרלוונטית לשבוע זה ותפורסם בזמנה!",
        reply_markup=build_back_button()
    )


async def mark_not_relevant_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User marks their post as not relevant anymore."""
    query = update.callback_query
    await query.answer()
    
    post_id = int(query.data.replace("not_relevant_", ""))
    
    set_post_relevance(post_id, False)
    
    await query.edit_message_text(
        "✅ המודעה שלך לא תפורסם השבוע.",
        reply_markup=build_back_button()
    )


async def my_posts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows user's own posts: /myposts"""
    user_id = update.effective_user.id
    
    from db_operations import get_user_posts
    posts = get_user_posts(user_id)
    
    if not posts:
        await update.message.reply_text("אין לך מודעות פעילות במערכת.", reply_markup=build_back_button())
        return
    
    for post in posts:
        status = "✅ מאושרת" if post.is_approved_by_admin else "⏳ ממתינה לאישור"
        keyboard = [
            [
                InlineKeyboardButton("✏️ ערוך", callback_data=f"edit_post_{post.id}"),
                InlineKeyboardButton("🗑️ מחק", callback_data=f"delete_post_{post.id}")
            ],
            [InlineKeyboardButton("🏠 חזרה לתפריט", callback_data="main_menu")]
        ]
        
        await update.message.reply_text(
            f"📦 מודעה #{post.id}\n\n{post.content}\n\nסטטוס: {status}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def my_posts_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback for my posts button."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    from db_operations import get_user_posts
    posts = get_user_posts(user_id)
    
    if not posts:
        await query.edit_message_text("אין לך מודעות פעילות במערכת.", reply_markup=build_back_button())
        return
    
    await query.edit_message_text("הנה המודעות שלך:", reply_markup=build_back_button())
    
    for post in posts:
        status = "✅ מאושרת" if post.is_approved_by_admin else "⏳ ממתינה לאישור"
        keyboard = [
            [
                InlineKeyboardButton("✏️ ערוך", callback_data=f"edit_post_{post.id}"),
                InlineKeyboardButton("🗑️ מחק", callback_data=f"delete_post_{post.id}")
            ],
            [InlineKeyboardButton("🏠 חזרה לתפריט", callback_data="main_menu")]
        ]
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"📦 מודעה #{post.id}\n\n{post.content}\n\nסטטוס: {status}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def edit_post_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback for edit post button."""
    query = update.callback_query
    await query.answer()
    
    post_id = int(query.data.replace("edit_post_", ""))
    
    from db_operations import get_sell_post
    post = get_sell_post(post_id)
    
    if not post or post.user_id != query.from_user.id:
        await query.edit_message_text("לא נמצאה מודעה או שאין לך הרשאה לערוך אותה.")
        return
    
    context.user_data['editing_post_id'] = post_id
    
    keyboard = [[InlineKeyboardButton("❌ ביטול", callback_data="cancel_edit_post")]]
    await query.edit_message_text(
        f"המודעה הנוכחית:\n{post.content}\n\nשלח את התוכן החדש:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return AWAITING_EDIT_CONTENT


async def receive_edit_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives edited content for a post."""
    post_id = context.user_data.get('editing_post_id')
    if not post_id:
        return ConversationHandler.END
    
    new_content = update.message.text
    user_id = update.effective_user.id
    
    from db_operations import update_sell_post, get_sell_post
    post = get_sell_post(post_id)
    
    if not post or post.user_id != user_id:
        await update.message.reply_text("שגיאה בעדכון המודעה.")
        return ConversationHandler.END
    
    updated_post = update_sell_post(post_id, new_content)
    
    await update.message.reply_text(
        "✅ המודעה עודכנה ונשלחה לאישור מחדש!",
        reply_markup=build_back_button()
    )
    
    if ADMIN_CHAT_ID:
        try:
            user = get_user(user_id)
            admin_message = f"""📝 עדכון מודעה:

👤 מפרסם: {user.full_name if user else 'לא ידוע'}
🆔 ID: {user_id}
📦 מודעה #{post_id}

📝 תוכן חדש:
{new_content}"""
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ אשר", callback_data=f"approve_post_{post_id}"),
                    InlineKeyboardButton("❌ דחה", callback_data=f"reject_post_{post_id}")
                ]
            ]
            
            await context.bot.send_message(
                chat_id=int(ADMIN_CHAT_ID),
                text=admin_message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Failed to send edit notification to admin: {e}")
    
    context.user_data.pop('editing_post_id', None)
    return ConversationHandler.END


async def cancel_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel edit post."""
    query = update.callback_query
    await query.answer()
    context.user_data.pop('editing_post_id', None)
    await query.edit_message_text("עריכת המודעה בוטלה.", reply_markup=build_back_button())
    return ConversationHandler.END


async def delete_post_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback for delete post button."""
    query = update.callback_query
    await query.answer()
    
    post_id = int(query.data.replace("delete_post_", ""))
    
    from db_operations import get_sell_post
    post = get_sell_post(post_id)
    
    if not post or post.user_id != query.from_user.id:
        await query.edit_message_text("לא נמצאה מודעה או שאין לך הרשאה למחוק אותה.")
        return
    
    keyboard = [
        [
            InlineKeyboardButton("✅ כן, מחק", callback_data=f"confirm_delete_{post_id}"),
            InlineKeyboardButton("❌ לא", callback_data=f"cancel_delete_{post_id}")
        ]
    ]
    
    await query.edit_message_text(
        f"האם אתה בטוח שברצונך למחוק את המודעה?\n\n{post.content}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def confirm_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm delete post."""
    query = update.callback_query
    await query.answer()
    
    post_id = int(query.data.replace("confirm_delete_", ""))
    
    from db_operations import delete_sell_post, get_sell_post
    post = get_sell_post(post_id)
    
    if not post or post.user_id != query.from_user.id:
        await query.edit_message_text("שגיאה במחיקת המודעה.")
        return
    
    delete_sell_post(post_id)
    await query.edit_message_text("✅ המודעה נמחקה בהצלחה.", reply_markup=build_back_button())


async def cancel_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel delete post."""
    query = update.callback_query
    await query.answer()
    
    post_id = int(query.data.replace("cancel_delete_", ""))
    
    from db_operations import get_sell_post
    post = get_sell_post(post_id)
    
    if post:
        status = "✅ מאושרת" if post.is_approved_by_admin else "⏳ ממתינה לאישור"
        keyboard = [
            [
                InlineKeyboardButton("✏️ ערוך", callback_data=f"edit_post_{post_id}"),
                InlineKeyboardButton("🗑️ מחק", callback_data=f"delete_post_{post_id}")
            ],
            [InlineKeyboardButton("🏠 חזרה לתפריט", callback_data="main_menu")]
        ]
        await query.edit_message_text(
            f"📦 מודעה #{post_id}\n\n{post.content}\n\nסטטוס: {status}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await query.edit_message_text("המודעה לא נמצאה.", reply_markup=build_back_button())


AWAITING_EDIT_CONTENT = 10


def setup_selling_handlers(application: Application):
    """Sets up all selling post handlers."""
    
    sell_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("sell", new_sell_post_command)],
        states={
            AWAITING_SELL_CONTENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_sell_post_content),
                MessageHandler(filters.PHOTO | filters.VIDEO, receive_sell_post_content),
                CallbackQueryHandler(cancel_sell_callback, pattern="^cancel_sell$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", lambda u, c: ConversationHandler.END),
            CallbackQueryHandler(cancel_sell_callback, pattern="^cancel_sell$"),
        ],
        allow_reentry=True,
        per_chat=True,
        per_user=True
    )
    
    edit_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_post_callback, pattern="^edit_post_")],
        states={
            AWAITING_EDIT_CONTENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_edit_content),
                CallbackQueryHandler(cancel_edit_callback, pattern="^cancel_edit_post$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_edit_callback, pattern="^cancel_edit_post$"),
        ],
        allow_reentry=True,
        per_chat=True,
        per_user=True
    )
    
    application.add_handler(sell_conv_handler)
    application.add_handler(edit_conv_handler)
    application.add_handler(CommandHandler("myposts", my_posts_command))
    application.add_handler(CallbackQueryHandler(my_posts_callback, pattern="^my_posts$"))
    application.add_handler(CallbackQueryHandler(approve_post_callback, pattern="^approve_post_"))
    application.add_handler(CallbackQueryHandler(reject_post_callback, pattern="^reject_post_"))
    application.add_handler(CallbackQueryHandler(delete_post_callback, pattern="^delete_post_"))
    application.add_handler(CallbackQueryHandler(confirm_delete_callback, pattern="^confirm_delete_"))
    application.add_handler(CallbackQueryHandler(cancel_delete_callback, pattern="^cancel_delete_"))
    application.add_handler(CallbackQueryHandler(handle_relevance_callback, pattern="^(relevant_|irrelevant_)"))
    application.add_handler(CallbackQueryHandler(set_day_callback, pattern="^set_day_"))
    application.add_handler(CallbackQueryHandler(set_slot_callback, pattern="^set_slot_"))
    application.add_handler(CallbackQueryHandler(confirm_relevance_callback, pattern="^confirm_relevant_"))
    application.add_handler(CallbackQueryHandler(mark_not_relevant_callback, pattern="^not_relevant_"))
    
    logger.info("Selling handlers setup complete")
