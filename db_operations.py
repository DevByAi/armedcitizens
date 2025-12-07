import os
from contextlib import contextmanager
from typing import Union, List  # ייבוא Union ו-List לתאימות ל-Python 3.8

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# יש לוודא ש-Base, User ו-SellPost מיובאים נכון מהקובץ db_models
from db_models import Base, User, SellPost 


# קבלת משתנה הסביבה DB_URL
DB_URL = os.getenv("DB_URL")

# ודא שה-DB_URL קיים
if not DB_URL:
    raise ValueError("DB_URL environment variable is not set!")

# יצירת מנוע חיבור ל-DB
engine = create_engine(DB_URL, echo=False)

# יצירת מחלקה Session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db(db_url: str):
    """יוצר את הטבלאות בבסיס הנתונים."""
    print("Initializing database...")
    Base.metadata.create_all(bind=engine)
    print("Database initialization complete.")

@contextmanager
def get_db() -> Session:
    """קונטקסט מנג'ר ליצירת Session ל-DB וסגירתו אוטומטית."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ----------------------------------------------------------------------
# פונקציות לניהול משתמשים
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
            # יצירת משתמש חדש
            user = User(telegram_id=telegram_id, **kwargs)
            db.add(user)
        else:
            # עדכון משתמש קיים
            for key, value in kwargs.items():
                setattr(user, key, value)
        
        db.commit()
        db.refresh(user)
        return user

def ban_user_in_db(telegram_id: int):
    """מסמן משתמש כחסום ומבטל את אישורו. (פונקציה זו נוספה לפתרון ה-ImportError)."""
    with get_db() as db:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if user:
            user.is_banned = True
            user.is_approved = False
            db.commit()

# ----------------------------------------------------------------------
# פונקציות לניהול מודעות מכירה
# ----------------------------------------------------------------------

def get_posts_by_status(status: str) -> Union[List[SellPost], None]:
    """מחזיר מודעות לפי סטטוס."""
    with get_db() as db:
        posts = db.query(SellPost).filter(SellPost.status == status).all()
        return posts if posts else None

def create_sell_post(telegram_id: int, text: str) -> SellPost:
    """יוצר מודעת מכירה חדשה."""
    with get_db() as db:
        post = SellPost(user_id=telegram_id, text=text, status="pending")
        db.add(post)
        db.commit()
        db.refresh(post)
        return post
