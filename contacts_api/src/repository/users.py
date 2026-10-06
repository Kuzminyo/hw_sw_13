from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.models import User
from src.schemas import UserCreate


def get_user_by_email(email: str, db: Session) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


def create_user(body: UserCreate, hashed_password: str, db: Session) -> User:
    user = User(username=body.username, email=body.email.lower(), password=hashed_password)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_refresh_token(user: User, token: str | None, db: Session) -> None:
    user.refresh_token = token
    db.commit()


def confirm_email(user: User, db: Session) -> None:
    user.confirmed = True
    db.commit()


def update_avatar(user: User, url: str, db: Session) -> User:
    user.avatar = url
    db.commit()
    db.refresh(user)
    return user


def update_password(user: User, hashed_password: str, db: Session) -> None:
    """Set a new password and log out everywhere by revoking the refresh token.

    The reset link was delivered to the user's mailbox, so the email counts as confirmed.
    """
    user.password = hashed_password
    user.refresh_token = None
    user.confirmed = True
    db.commit()
