# ==================================
# קובץ: db_operations.py (מתוקן ומלא)
# ==================================
import logging
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.exc import SQLAlchemyError
from db_models import engine, User, SellPost  # וודא ש-SellPost קיים ב-db_models שלך

# יצירת Session מנוהל
session_factory = sessionmaker(bind=engine)
Session = scoped_session(session_factory)
logger = logging.getLogger(__name__)

def get_session():
    return Session()

# --- פונקציות משתמשים (Users) ---

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
    """מחזיר רשימה של כל המשתמשים שממתינים לאישור"""
    session = Session()
    try:
        return session.query(User).filter_by(is_approved=False, is_banned=False).all()
    finally:
        session.close()

def get_all_admins():
    """מחזיר רשימה של כל האדמינים"""
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

# --- פונקציות מודעות מכירה (Sell Posts) ---

def get_pending_sell_posts():
    """מחזיר את כל מודעות המכירה שממתינות לאישור"""
    session = Session()
    try:
        # מניח שיש עמודה is_approved בטבלת SellPost
        return session.query(SellPost).filter_by(is_approved=False).all()
    except Exception as e:
        logger.error(f"Error fetching pending posts: {e}")
        return []
    finally:
        session.close()

def get_approved_posts():
    """מחזיר את כל מודעות המכירה המאושרות"""
    session = Session()
    try:
        return session.query(SellPost).filter_by(is_approved=True).all()
    except Exception as e:
        logger.error(f"Error fetching approved posts: {e}")
        return []
    finally:
        session.close()

# הערה: אם אתה משתמש במודל אחר למודעות (לא SellPost), שנה את השם בהתאם.
