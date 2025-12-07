import os
from contextlib import contextmanager
from typing import Union, List, Optional # Optional הוא דרך נוספת לכתוב Union[T, None]
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import DeclarativeMeta
from sqlalchemy.exc import SQLAlchemyError

# יש לוודא ש-Base, User ו-SellPost מיובאים נכון מהקובץ db_models
from db_models import Base, User, SellPost 


# קבלת משתנה הסביבה DB_URL
DB_URL = os.getenv("DB_URL")

if not DB_URL:
    # אם ה-DB_URL לא מוגדר, הקריסה תתרחש כאן עם הודעה ברורה
    raise ValueError("DB_URL environment variable is not set!")

# יצירת מנוע חיבור ל-DB
engine = create_engine(DB_URL, echo=False)

# יצירת מחלקה Session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """יוצר את הטבלאות בבסיס הנתונים ומטפל בשגיאות."""
    print("Initializing database...")
    try:
        if isinstance(Base, DeclarativeMeta):
            Base.metadata.create_all(bind=engine)
            print("Database initialization complete.")
        else:
            print("Error: Base is not a DeclarativeMeta instance.")
    except SQLAlchemyError as e:
        print(f"FATAL DB ERROR during init: {e}")
        # אם יש כשל כאן (כמו הרשאה או חיבור שגוי), הוא יפיל את ה-Worker
        raise

@contextmanager
def get_db() -> Session:
    """קונטקסט מנג'ר ליצירת Session ל-DB וסגירתו אוטומטית."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ----------------------------------------------------------------------
# פונקציות לניהול משתמשים ואימות
# ----------------------------------------------------------------------

def get_user(telegram_id: int) -> Union[User, None]:
    with get_db() as db:
        return db.query(User).filter(User.telegram_id == telegram_id).first()

def create_or_update_user(telegram_id: int, **kwargs) -> User:
    with get_db() as db:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
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
    """מחזיר רשימת כל המשתמשים המסומנים כמנהלים."""
    with get_db() as db:
        return db.query(User).filter(User.is_admin == True).all()

def get_all_pending_users() -> List[User]:
    """מחזיר רשימת משתמשים הממתינים לאימות."""
    with get_db() as db:
        return db.query(User).filter(User.is_approved == False, User.is_banned == False).all()


# ----------------------------------------------------------------------
# פונקציות לניהול מודעות מכירה (הפונקציות החסרות)
# ----------------------------------------------------------------------

# הפונקציה החסרה שגרמה לקריסה:
def add_sell_post(user_id: int, content: str) -> SellPost:
    """מוסיף מודעת מכירה חדשה."""
    with get_db() as db:
        post = SellPost(user_id=user_id, content=content, is_approved_by_admin=False)
        db.add(post)
        db.commit()
        db.refresh(post)
        return post

# ודא שכל הפונקציות הבאות שנדרשו לייבוא קיימות:

def get_approved_posts() -> List[SellPost]:
    """שולף מודעות פעילות ומאושרות לשליחה שבועית."""
    with get_db() as db:
        return db.query(SellPost).filter(
            SellPost.is_active == True,
            SellPost.is_approved_by_admin == True
        ).all()

def set_post_relevance(post_id: int, is_relevant: bool):
    """מעדכן סטטוס רלוונטיות המודעה."""
    with get_db() as db:
        post = db.query(SellPost).filter(SellPost.id == post_id).first()
        if post:
            post.is_active = is_relevant
            if is_relevant:
                 post.last_sent_date = datetime.now() # אם רלוונטי, עדכן תאריך שליחה
            db.commit()
            
def get_available_slots_for_day():
    """פונקציית Placeholder למציאת סלוטים - נחוצה לייבוא."""
    return [] # Placeholder, הלוגיקה המלאה נמצאת ב-handlers

def set_post_time_slot(post_id: int, slot_info: str):
    """פונקציית Placeholder להגדרת זמן שליחה - נחוצה לייבוא."""
    pass
    
def set_post_publication_day(post_id: int, day: str):
    """פונקציית Placeholder להגדרת יום פרסום - נחוצה לייבוא."""
    pass
