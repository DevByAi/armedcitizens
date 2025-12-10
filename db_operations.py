# ==================================
# קובץ: db_operations.py (מלא)
# ==================================
from db_models import User, SellPost, get_db_session
from sqlalchemy.orm import Session
from contextlib import contextmanager
from typing import Union, List
from datetime import datetime, timedelta


@contextmanager
def get_db() -> Session:
    """קונטקסט מנג'ר ליצירת Session ל-DB וסגירתו אוטומטית."""
    with get_db_session() as db:
        yield db

# ----------------------------------------------------------------------
# פונקציות לניהול משתמשים ואימות
# ----------------------------------------------------------------------

def get_user(telegram_id: int) -> Union[User, None]:
    with get_db() as db:
        return db.query(User).filter(User.telegram_id == telegram_id).first()

def create_or_update_user(telegram_id: int, **kwargs) -> User:
    with get_db() as db:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if user is None:
            user = User(telegram_id=telegram_id, **kwargs)
            db.add(user)
        else:
            for key, value in kwargs.items():
                setattr(user, key, value)
        db.commit()
        db.refresh(user)
        return user

def ban_user_in_db(telegram_id: int):
    with get_db() as db:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if user:
            user.is_banned = True
            user.is_approved = False
            db.commit()

def get_all_admins() -> List[User]:
    with get_db() as db:
        return db.query(User).filter(User.is_admin == True).all()

def set_user_admin(telegram_id: int, is_admin: bool) -> bool:
    with get_db() as db:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if user is None:
            user = User(telegram_id=telegram_id, is_admin=is_admin)
            db.add(user)
        else:
            user.is_admin = is_admin
        db.commit()
        return True
        
def get_all_pending_users() -> List[User]:
    with get_db() as db:
        return db.query(User).filter(
            User.is_approved == False,
            User.is_banned == False
        ).all()

# ----------------------------------------------------------------------
# פונקציות לניהול מודעות מכירה 
# ----------------------------------------------------------------------

def add_sell_post(user_id: int, content: str) -> SellPost:
    with get_db() as db:
        post = SellPost(user_id=user_id, content=content, is_approved_by_admin=False)
        db.add(post)
        db.commit()
        db.refresh(post)
        return post

def get_user_posts(user_id: int) -> List[SellPost]:
    """שולף את כל המודעות הפעילות של משתמש נתון (נדרש על ידי selling.py)."""
    with get_db() as db:
        return db.query(SellPost).filter(
            SellPost.user_id == user_id,
            SellPost.is_active == True
        ).all()
        
def get_sell_post(post_id: int) -> Union[SellPost, None]:
    """שולף מודעת מכירה לפי ID."""
    with get_db() as db:
        return db.query(SellPost).filter(SellPost.id == post_id).first()

def update_sell_post(post_id: int, content: str) -> Union[SellPost, None]:
    """מעדכן תוכן מודעה ומחזיר למצב ממתין לאישור."""
    with get_db() as db:
        post = db.query(SellPost).filter(SellPost.id == post_id).first()
        if post:
            post.content = content
            post.is_approved_by_admin = False
            db.commit()
            db.refresh(post)
        return post


def delete_sell_post(post_id: int) -> bool:
    """מסמן מודעה כלא פעילה (soft delete)."""
    with get_db() as db:
        post = db.query(SellPost).filter(SellPost.id == post_id).first()
        if post:
            post.is_active = False
            db.commit()
            return True
        return False

def get_pending_sell_posts() -> List[SellPost]:
    """שולף את כל המודעות הממתינות לאישור אדמין."""
    with get_db() as db:
        return db.query(SellPost).filter(
            SellPost.is_active == True,
            SellPost.is_approved_by_admin == False
        ).all()
