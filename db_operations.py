# ==================================
# קובץ: db_operations.py (מאוחד ומתוקן)
# ==================================
from db_models import User, SellPost
from sqlalchemy.orm import Session
from contextlib import contextmanager
from typing import Union, List, Optional
from datetime import datetime, timedelta

# פונקציות ה-DBSession מגיעות מ-db_models
from db_models import get_db_session 


@contextmanager
def get_db() -> Session:
    """קונטקסט מנג'ר ליצירת Session ל-DB וסגירתו אוטומטית."""
    with get_db_session() as db:
        yield db

# ----------------------------------------------------------------------
# פונקציות לניהול משתמשים ואימות
# ----------------------------------------------------------------------

def get_user(telegram_id: int) -> Union[User, None]:
    """מחזיר משתמש לפי ID טלגרם, או None אם לא נמצא."""
    with get_db() as db:
        return db.query(User).filter(User.telegram_id == telegram_id).first()

def create_or_update_user(telegram_id: int, **kwargs) -> User:
    """יוצר או מעדכן משתמש קיים."""
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
    """מסמן משתמש כחסום ומבטל את אישורו."""
    with get_db() as db:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if user:
            user.is_banned = True
            user.is_approved = False
            db.commit()

def get_all_admins() -> List[User]:
    """מחזיר רשימת כל המשתמשים המסומנים כמנהלים."""
    with get_db() as db:
        return db.query(User).filter(User.is_admin == True).all()

def set_user_admin(telegram_id: int, is_admin: bool) -> bool:
    """משנה את סטטוס הניהול של משתמש. יוצר משתמש אם לא קיים."""
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
    """מחזיר רשימת משתמשים הממתינים לאימות."""
    with get_db() as db:
        return db.query(User).filter(
            User.is_approved == False,
            User.is_banned == False
        ).all()
    

# ----------------------------------------------------------------------
# פונקציות לניהול מודעות מכירה
# ----------------------------------------------------------------------

def add_sell_post(user_id: int, content: str) -> SellPost:
    """מוסיף מודעת מכירה חדשה."""
    with get_db() as db:
        post = SellPost(user_id=user_id, content=content, is_approved_by_admin=False)
        db.add(post)
        db.commit()
        db.refresh(post)
        return post

def get_approved_posts() -> List[SellPost]:
    """שולף מודעות פעילות ומאושרות לשליחה שבועית."""
    with get_db() as db:
        return db.query(SellPost).filter(
            SellPost.is_active == True,
            SellPost.is_approved_by_admin == True
        ).all()

def set_post_publication_day(post_id: int, day: int) -> Union[SellPost, None]:
    """Set the publication day (0-5) for a post."""
    with get_db() as db:
        post = db.query(SellPost).filter(SellPost.id == post_id).first()
        if post:
            post.publication_day = day
            db.commit()
            db.refresh(post)
        return post

def set_post_relevance(post_id: int, is_relevant: bool) -> Union[SellPost, None]:
    """מעדכן סטטוס רלוונטיות המודעה."""
    with get_db() as db:
        post = db.query(SellPost).filter(SellPost.id == post_id).first()
        if post:
            post.is_relevant_this_week = is_relevant
            db.commit()
            db.refresh(post)
        return post

def reset_weekly_relevance():
    """Reset is_relevant_this_week to False for all active posts at start of week."""
    with get_db() as db:
        db.query(SellPost).filter(SellPost.is_active == True).update(
            {SellPost.is_relevant_this_week: False}
        )
        db.commit()

def get_posts_needing_relevance_check() -> List[SellPost]:
    """Get all active approved posts that need relevance confirmation."""
    with get_db() as db:
        return db.query(SellPost).filter(
            SellPost.is_active == True,
            SellPost.is_approved_by_admin == True
        ).all()

# Time slot constants - 15 slots from 8am to 10pm
TIME_SLOTS = list(range(8, 23))  # 8, 9, 10, ..., 22

def get_taken_slots_for_day(day: int) -> List[int]:
    """Get list of time slots that are already taken for a specific day."""
    with get_db() as db:
        posts = db.query(SellPost).filter(
            SellPost.is_active == True,
            SellPost.publication_day == day,
            SellPost.time_slot != None
        ).all()
        return [p.time_slot for p in posts if p.time_slot is not None]


def get_available_slots_for_day(day: int) -> List[int]:
    """Get list of available time slots for a specific day."""
    taken = get_taken_slots_for_day(day)
    return [slot for slot in TIME_SLOTS if slot not in taken]


def set_post_time_slot(post_id: int, time_slot: int) -> Union[SellPost, None]:
    """Set the time slot for a post."""
    with get_db() as db:
        post = db.query(SellPost).filter(SellPost.id == post_id).first()
        if post:
            post.time_slot = time_slot
            db.commit()
            db.refresh(post)
        return post


def get_posts_for_hour(day: int, hour: int) -> List[SellPost]:
    """Get posts that should be published at a specific day and hour."""
    
    with get_db() as db:
        one_week_ago = datetime.now() - timedelta(days=7)
        
        posts_to_publish = db.query(SellPost).filter(
            SellPost.is_active == True,
            SellPost.is_approved_by_admin == True,
            SellPost.is_relevant_this_week == True,
            SellPost.publication_day == day,
            SellPost.time_slot == hour,
            (SellPost.last_sent_date == None) | (SellPost.last_sent_date < one_week_ago)
        ).all()
        
        return posts_to_publish
