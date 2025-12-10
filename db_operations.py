# ==================================
# קובץ: db_operations.py (מלא - משתמשים + מכירות + אדמין)
# ==================================
import logging
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.exc import SQLAlchemyError
from db_models import engine, User, SellPost 

# יצירת Session מנוהל
session_factory = sessionmaker(bind=engine)
Session = scoped_session(session_factory)
logger = logging.getLogger(__name__)

def get_session():
    return Session()

# ---------------------------------------------------------
# 👤 ניהול משתמשים (Users)
# ---------------------------------------------------------

def create_or_update_user(telegram_id, username=None, full_name=None, is_approved=None):
    session = Session()
    try:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            user = User(telegram_id=telegram_id)
            session.add(user)
        
        if username: user.username = username
        if full_name: user.full_name = full_name
        if is_approved is not None: user.is_approved = is_approved
        
        session.commit()
        return user
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error creating/updating user {telegram_id}: {e}")
    finally:
        session.close()

def get_user(telegram_id):
    session = Session()
    try:
        return session.query(User).filter_by(telegram_id=telegram_id).first()
    finally:
        session.close()

def get_all_pending_users():
    session = Session()
    try:
        return session.query(User).filter_by(is_approved=False, is_banned=False).all()
    finally:
        session.close()

def get_all_admins():
    session = Session()
    try:
        return session.query(User).filter_by(is_admin=True).all()
    finally:
        session.close()

def set_user_admin(telegram_id, is_admin):
    session = Session()
    try:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if user:
            user.is_admin = is_admin
            session.commit()
            return True
        return False
    except SQLAlchemyError:
        session.rollback()
        return False
    finally:
        session.close()

def ban_user_in_db(telegram_id):
    session = Session()
    try:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if user:
            user.is_banned = True
            user.is_approved = False
            session.commit()
    except SQLAlchemyError:
        session.rollback()
    finally:
        session.close()

# ---------------------------------------------------------
# 📦 ניהול מודעות מכירה (Sell Posts) - החלק שהיה חסר
# ---------------------------------------------------------

def add_sell_post(user_id, description, price, contact_info, image_id):
    """יוצר מודעת מכירה חדשה"""
    session = Session()
    try:
        new_post = SellPost(
            user_id=user_id,
            description=description,
            price=price,
            contact_info=contact_info,
            image_id=image_id,
            is_approved=False, # ברירת מחדל: ממתין לאישור
            status='active'
        )
        session.add(new_post)
        session.commit()
        # מרעננים כדי לקבל את ה-ID החדש
        session.refresh(new_post)
        return new_post
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error adding sell post: {e}")
        return None
    finally:
        session.close()

def get_sell_post(post_id):
    """שולף מודעה לפי ID"""
    session = Session()
    try:
        return session.query(SellPost).filter_by(id=post_id).first()
    finally:
        session.close()

def get_user_posts(user_id):
    """שולף את כל המודעות של משתמש מסוים"""
    session = Session()
    try:
        return session.query(SellPost).filter_by(user_id=user_id).all()
    finally:
        session.close()

def update_sell_post(post_id, **kwargs):
    """מעדכן שדות במודעה קיימת"""
    session = Session()
    try:
        post = session.query(SellPost).filter_by(id=post_id).first()
        if post:
            for key, value in kwargs.items():
                if hasattr(post, key):
                    setattr(post, key, value)
            session.commit()
            return True
        return False
    except SQLAlchemyError:
        session.rollback()
        return False
    finally:
        session.close()

def delete_sell_post(post_id):
    """מוחק מודעה (או מסמן כ-deleted)"""
    session = Session()
    try:
        post = session.query(SellPost).filter_by(id=post_id).first()
        if post:
            session.delete(post) # מחיקה פיזית
            # או: post.status = 'deleted' אם רוצים לשמור היסטוריה
            session.commit()
            return True
        return False
    except SQLAlchemyError:
        session.rollback()
        return False
    finally:
        session.close()

def get_pending_sell_posts():
    """עבור אדמין: שליפת כל המודעות הממתינות לאישור"""
    session = Session()
    try:
        return session.query(SellPost).filter_by(is_approved=False, status='active').all()
    except Exception as e:
        logger.error(f"Error fetching pending posts: {e}")
        return []
    finally:
        session.close()

def get_approved_posts():
    """שליפת כל המודעות המאושרות"""
    session = Session()
    try:
        return session.query(SellPost).filter_by(is_approved=True, status='active').all()
    except Exception as e:
        logger.error(f"Error fetching approved posts: {e}")
        return []
    finally:
        session.close()
