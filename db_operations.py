from db_models import User, SellPost, get_db_session
from sqlalchemy.orm import Session
from contextlib import contextmanager

@contextmanager
def get_db():
    with get_db_session() as db:
        yield db

def get_user(telegram_id: int) -> User | None:
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

def add_sell_post(user_id: int, content: str) -> SellPost:
    with get_db() as db:
        post = SellPost(user_id=user_id, content=content, is_approved_by_admin=False)
        db.add(post)
        db.commit()
        db.refresh(post)
        return post

def get_approved_posts() -> list[SellPost]:
    with get_db() as db:
        return db.query(SellPost).filter(
            SellPost.is_active == True,
            SellPost.is_approved_by_admin == True
        ).all()

def get_all_admins() -> list[User]:
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

def get_all_pending_users() -> list[User]:
    with get_db() as db:
        return db.query(User).filter(
            User.is_approved == False,
            User.is_banned == False
        ).all()
    


def approve_sell_post(post_id: int) -> SellPost | None:
    with get_db() as db:
        post = db.query(SellPost).filter(SellPost.id == post_id).first()
        if post:
            post.is_approved_by_admin = True
            db.commit()
            db.refresh(post)
        return post


def reject_sell_post(post_id: int) -> SellPost | None:
    with get_db() as db:
        post = db.query(SellPost).filter(SellPost.id == post_id).first()
        if post:
            post.is_active = False
            db.commit()
            db.refresh(post)
        return post


def get_pending_sell_posts() -> list[SellPost]:
    with get_db() as db:
        return db.query(SellPost).filter(
            SellPost.is_active == True,
            SellPost.is_approved_by_admin == False
        ).all()


def get_user_posts(user_id: int) -> list[SellPost]:
    with get_db() as db:
        return db.query(SellPost).filter(
            SellPost.user_id == user_id,
            SellPost.is_active == True
        ).all()


def get_sell_post(post_id: int) -> SellPost | None:
    with get_db() as db:
        return db.query(SellPost).filter(SellPost.id == post_id).first()


def update_sell_post(post_id: int, content: str) -> SellPost | None:
    with get_db() as db:
        post = db.query(SellPost).filter(SellPost.id == post_id).first()
        if post:
            post.content = content
            post.is_approved_by_admin = False
            db.commit()
            db.refresh(post)
        return post


def delete_sell_post(post_id: int) -> bool:
    with get_db() as db:
        post = db.query(SellPost).filter(SellPost.id == post_id).first()
        if post:
            post.is_active = False
            db.commit()
            return True
        return False


def set_post_publication_day(post_id: int, day: int) -> SellPost | None:
    with get_db() as db:
        post = db.query(SellPost).filter(SellPost.id == post_id).first()
        if post:
            post.publication_day = day
            db.commit()
            db.refresh(post)
        return post


def set_post_relevance(post_id: int, is_relevant: bool) -> SellPost | None:
    with get_db() as db:
        post = db.query(SellPost).filter(SellPost.id == post_id).first()
        if post:
            post.is_relevant_this_week = is_relevant
            db.commit()
            db.refresh(post)
        return post


def reset_all_posts_relevance():
    with get_db() as db:
        db.query(SellPost).filter(SellPost.is_active == True).update({SellPost.is_relevant_this_week: False})
        db.commit()


def get_posts_for_day(day: int) -> list[SellPost]:
    with get_db() as db:
        return db.query(SellPost).filter(
            SellPost.is_active == True,
            SellPost.is_approved_by_admin == True,
            SellPost.is_relevant_this_week == True,
            SellPost.publication_day == day
        ).all()


def get_posts_needing_relevance_confirmation() -> list[SellPost]:
    with get_db() as db:
        return db.query(SellPost).filter(
            SellPost.is_active == True,
            SellPost.is_approved_by_admin == True,
            SellPost.is_relevant_this_week == False
        ).all()


def get_posts_needing_relevance_check() -> list[SellPost]:
    """Get all active approved posts that need relevance confirmation."""
    with get_db() as db:
        return db.query(SellPost).filter(
            SellPost.is_active == True,
            SellPost.is_approved_by_admin == True
        ).all()


def reset_weekly_relevance():
    """Reset is_relevant_this_week to False for all active posts at start of week."""
    with get_db() as db:
        db.query(SellPost).filter(SellPost.is_active == True).update(
            {SellPost.is_relevant_this_week: False}
        )
        db.commit()


def get_posts_to_publish_today(day: int) -> list[SellPost]:
    """Get posts that should be published today (approved, relevant, not yet sent this week)."""
    from datetime import datetime, timedelta
    
    with get_db() as db:
        one_week_ago = datetime.now() - timedelta(days=7)
        return db.query(SellPost).filter(
            SellPost.is_active == True,
            SellPost.is_approved_by_admin == True,
            SellPost.is_relevant_this_week == True,
            SellPost.publication_day == day,
            (SellPost.last_sent_date == None) | (SellPost.last_sent_date < one_week_ago)
        ).all()


def mark_post_sent(post_id: int):
    """Mark a post as sent by updating last_sent_date."""
    from datetime import datetime
    
    with get_db() as db:
        post = db.query(SellPost).filter(SellPost.id == post_id).first()
        if post:
            post.last_sent_date = datetime.now()
            db.commit()


# Time slot constants - 15 slots from 8am to 10pm
TIME_SLOTS = list(range(8, 23))  # 8, 9, 10, ..., 22


def get_taken_slots_for_day(day: int) -> list[int]:
    """Get list of time slots that are already taken for a specific day.
    Includes ALL active posts with a slot (regardless of approval/relevance) to prevent overbooking."""
    with get_db() as db:
        posts = db.query(SellPost).filter(
            SellPost.is_active == True,
            SellPost.publication_day == day,
            SellPost.time_slot != None
        ).all()
        return [p.time_slot for p in posts if p.time_slot is not None]


def get_available_slots_for_day(day: int) -> list[int]:
    """Get list of available time slots for a specific day."""
    taken = get_taken_slots_for_day(day)
    return [slot for slot in TIME_SLOTS if slot not in taken]


def set_post_time_slot(post_id: int, time_slot: int) -> SellPost | None:
    """Set the time slot for a post."""
    with get_db() as db:
        post = db.query(SellPost).filter(SellPost.id == post_id).first()
        if post:
            post.time_slot = time_slot
            db.commit()
            db.refresh(post)
        return post


def get_posts_for_hour(day: int, hour: int) -> list[SellPost]:
    """Get posts that should be published at a specific day and hour.
    Also includes legacy posts without time_slot at hour 9 (default publish hour)."""
    from datetime import datetime, timedelta
    
    with get_db() as db:
        one_week_ago = datetime.now() - timedelta(days=7)
        
        posts_with_slot = db.query(SellPost).filter(
            SellPost.is_active == True,
            SellPost.is_approved_by_admin == True,
            SellPost.is_relevant_this_week == True,
            SellPost.publication_day == day,
            SellPost.time_slot == hour,
            (SellPost.last_sent_date == None) | (SellPost.last_sent_date < one_week_ago)
        ).all()
        
        legacy_posts = []
        if hour == 9:
            legacy_posts = db.query(SellPost).filter(
                SellPost.is_active == True,
                SellPost.is_approved_by_admin == True,
                SellPost.is_relevant_this_week == True,
                SellPost.publication_day == day,
                SellPost.time_slot == None,
                (SellPost.last_sent_date == None) | (SellPost.last_sent_date < one_week_ago)
            ).all()
        
        return posts_with_slot + legacy_posts

