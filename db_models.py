from sqlalchemy import create_engine, Column, Integer, BigInteger, String, Boolean, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
from contextlib import contextmanager

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    full_name = Column(String)
    phone_number = Column(String)
    license_photo_id = Column(String)
    is_approved = Column(Boolean, default=False, nullable=False)
    is_banned = Column(Boolean, default=False, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.now)

class SellPost(Base):
    __tablename__ = 'sell_posts'
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, nullable=False)
    content = Column(String, nullable=False)
    is_approved_by_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    last_sent_date = Column(DateTime)
    publication_day = Column(Integer, default=0)  # 0=Sunday, 1=Monday, ..., 5=Friday (no Saturday)
    time_slot = Column(Integer, default=None)  # Hour of day (8-22) when post should be published
    is_relevant_this_week = Column(Boolean, default=False)  # User must confirm each week
    created_at = Column(DateTime, default=datetime.now)

ENGINE = None
SessionLocal = None

def init_db(db_url):
    global ENGINE, SessionLocal
    ENGINE = create_engine(db_url)
    Base.metadata.create_all(ENGINE)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=ENGINE)

@contextmanager
def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

