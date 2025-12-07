import os
from contextlib import contextmanager
from typing import Union, List  # Union ו-List לתאימות ל-Python 3.8

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import DeclarativeMeta

# יש לוודא ש-Base, User ו-SellPost מיובאים נכון מהקובץ db_models
from db_models import Base, User, SellPost 


# קבלת משתנה הסביבה DB_URL
DB_URL = os.getenv("DB_URL")

if not DB_URL:
    raise ValueError("DB_URL environment variable is not set!")

# יצירת מנוע חיבור ל-DB
engine = create_engine(DB_URL, echo=False)  # מומלץ לכבות echo בייצור

# יצירת מחלקה Session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """יוצר את הטבלאות בבסיס הנתונים."""
    print("Initializing database...")
    # נניח ש-Base הוא המטדאטה שמיובא מ-db_models
    if isinstance(Base, DeclarativeMeta):
        Base.metadata.create_all(bind=engine)
        print("Database initialization complete.")
    else:
        print("Error: Base is not a DeclarativeMeta instance. Check db_models.py")

@contextmanager
def get_db() -> Session:
    """קונטקסט מנג'ר ליצירת Session ל-DB וסגירתו אוטומטית."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ----------------------------------------------------------------------
# פונקציות לניהול משתמשים ואימות (הפונקציות החסרות)
# ----------------------------------------------------------------------

def get_user(telegram_id: int) -> Union[User, None]:
    """מחזיר משתמש לפי ID טלגרם, או None אם לא נמצא."""
    with get_db() as db:
        return db.query(User).filter(User.telegram_id == telegram_id).first()

def create_or_update_user(telegram_id: int, **kwargs) -> User:
    """יוצר או מעדכן משתמש קיים."""
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
    """מסמן משתמש כחסום ומבטל את אישורו."""
    with get_db() as db:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if user:
            user.is_banned = True
            user.is_approved = False
            db.commit()

# --- פונקציות שחסרו ונדרשו לייבוא ---

def get_all_admins() -> List[User]:
    """מחזיר רשימת כל המשתמשים המסומנים כמנהלים."""
    with get_db() as db:
        return db.query(User).filter(User.is_admin == True).all()

def set_user_admin(telegram_id: int, is_admin: bool):
    """משנה את סטטוס הניהול של משתמש."""
    with get_db() as db:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if user:
            user.is_admin = is_admin
            db.commit()

def get_all_pending_users() -> List[User]:
    """מחזיר רשימת משתמשים הממתינים לאימות."""
    with get_db() as db:
        return db.query(User).filter(User.is_approved == False, User.is_banned == False).all()


# ----------------------------------------------------------------------
# פונקציות לניהול מודעות מכירה
# ----------------------------------------------------------------------

def get_approved_posts() -> List[SellPost]:
    """שולף מודעות פעילות ומאושרות לשליחה שבועית."""
    with get_db() as db:
        return db.query(SellPost).filter(
            SellPost.is_active == True,
            SellPost.is_approved_by_admin == True
        ).all()

# [יש לוודא שפונקציות כמו add_sell_post מומשו בגרסה שאתה משתמש בה]
# [הערה: פונקציה get_posts_by_status שונתה ל-get_approved_posts]
