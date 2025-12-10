# בתוך handlers/selling.py (בתוך הפונקציה sell_receive_content):

async def sell_receive_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """שומר את תוכן המודעה ושולח לאדמין לאישור."""
    post_content = update.message.text
    user_id = update.effective_user.id

    # 1. שמירה ב-DB (הקוד הזה תקין)
    post = add_sell_post(user_id, post_content)
    
    # 2. שליחה לאדמין לאישור: תיקון גישה לפרטי המשתמש
    
    # שימוש ב-Update.effective_user במקום קריאה ל-get_chat_member
    telegram_user = update.effective_user
    full_name = telegram_user.full_name or "לא צוין שם"
    username = f"@{telegram_user.username}" if telegram_user.username else "אין Username"
    
    message_to_admin = f"""📦 מודעת מכירה חדשה ממתינה:
    
    👤 מפרסם: {full_name} ({username})
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
            text=message_to_admin, # שימוש ב-text במקום caption
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Failed to send selling post request to admin chat {ADMIN_CHAT_ID}: {e}")
        # אם השליחה נכשלת (למשל, ADMIN_CHAT_ID שגוי), עדיין נגיב למשתמש
        await update.message.reply_text(f"❌ שגיאה בשליחת המודעה לאדמין. נסה שוב מאוחר יותר. (ID: {post.id})")
        return ConversationHandler.END


    # 3. תגובה למשתמש (הקוד הזה תקין)
    await update.message.reply_text(
        f"✅ המודעה נשלחה לאישור מנהל (Post ID: {post.id}). תקבל הודעה לאחר אישור.",
        reply_markup=build_main_menu_for_user(user_id)
    )
    
    return ConversationHandler.END
