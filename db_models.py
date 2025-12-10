# ==================================
# קובץ: db_models.py (קובץ מלא להחלפה)
# ==================================
from sqlalchemy import Column, Integer, String, Boolean, BigInteger, DateTime, ForeignKey, create_engine
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
import os

# הגדרת הבסיס למודלים
Base = declarative_base()

# --- משתנה גלובלי עבור המנוע ---
# קריטי: מאפשר לקבצים אחרים לייבא את engine בלי לקרוס
engine = None 

# --- מודל משתמש (User) ---
class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False) # חובה BigInteger ל-ID של טלגרם
    username = Column(String, nullable=True)
    full_name = Column(String, nullable=True)
    
    # הרשאות וסטטוסים
    is_approved = Column(Boolean, default=False) # האם אושר כחבר קהילה
    is_admin = Column(Boolean, default=False)    # האם מנהל מערכת
    is_banned = Column(Boolean, default=False)   # האם חסום
    
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<User {self.telegram_id} ({self.full_name})>"

# --- מודל מודעת מכירה (SellPost) ---
class SellPost(Base):
    __tablename__ = 'sell_posts'

    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('users.telegram_id')) # מקושר למשתמש המפרסם
    
    description = Column(String, nullable=False)
    price = Column(String, nullable=True)
    contact_info = Column(String, nullable=True)
    image_id = Column(String, nullable=True) # מזהה תמונה בשרתי טלגרם
    
    is_approved = Column(Boolean, default=False) # האם המודעה אושרה לפרסום
    status = Column(String, default='active')    # active, sold, deleted
    created_at = Column(DateTime, default=datetime.utcnow)

    # יחסים (לא חובה אבל עוזר בקוד)
    user = relationship("User")

    def __repr__(self):
        return f"<SellPost {self.id} by {self.user_id}>"

# --- פונקציית אתחול הדאטהבייס ---
def init_db(db_url):
    """
    מאתחל את החיבור לדאטהבייס ויוצר טבלאות אם הן לא קיימות.
    נקרא מתוך main.py בעלייה.
    """
    global engine # מעדכן את המשתנה הגלובלי שהגדרנו למעלה
    
    if not db_url:
        raise ValueError("Database URL is missing! Check environment variables.")

    # תיקון נפוץ ל-Render שנותן כתובת postgres:// במקום postgresql://
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    # יצירת המנוע
    engine = create_engine(db_url, echo=False)
    
    # יצירת הטבלאות בפועל (Create Tables)
    Base.metadata.create_all(engine)
    print("✅ Database tables created successfully.")
