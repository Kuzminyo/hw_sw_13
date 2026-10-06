import hashlib
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordBearer
from sqlalchemy.orm import Session

from src.conf.config import settings
from src.database.db import get_db
from src.database.models import User
from src.repository import users as repository_users
from src.services import cache

ACCESS_SCOPE = "access_token"
REFRESH_SCOPE = "refresh_token"
EMAIL_SCOPE = "email_token"
RESET_SCOPE = "reset_password"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
refresh_scheme = HTTPBearer(auto_error=False)


# ---------- passwords ----------

def hash_password(password: str) -> str:
    # bcrypt only uses the first 72 bytes of the password
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8")[:72], hashed_password.encode("utf-8"))


# compared against when the email is unknown, to keep login timing the same
DUMMY_HASH = hash_password("dummy-password-for-timing")


# ---------- tokens ----------

def _create_token(email: str, scope: str, expires_delta: timedelta, **claims) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": email, "scope": scope, "iat": now, "exp": now + expires_delta, **claims}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(email: str) -> str:
    return _create_token(
        email, ACCESS_SCOPE, timedelta(minutes=settings.access_token_expire_minutes)
    )


def create_refresh_token(email: str) -> str:
    return _create_token(
        email, REFRESH_SCOPE, timedelta(days=settings.refresh_token_expire_days)
    )


def create_email_token(email: str) -> str:
    return _create_token(
        email, EMAIL_SCOPE, timedelta(hours=settings.email_token_expire_hours)
    )


def password_fingerprint(hashed_password: str) -> str:
    """Short digest of the current hash: a reset token stops working once the password changes."""
    return hashlib.sha256(hashed_password.encode("utf-8")).hexdigest()[:16]


def create_reset_token(email: str, hashed_password: str) -> str:
    return _create_token(
        email,
        RESET_SCOPE,
        timedelta(minutes=settings.reset_token_expire_minutes),
        pwd=password_fingerprint(hashed_password),
    )


def decode_token(token: str, expected_scope: str) -> str:
    """Return the email (sub) from a valid token of the expected scope, else raise 401."""
    return decode_token_payload(token, expected_scope)["sub"]


def decode_token_payload(token: str, expected_scope: str) -> dict:
    """Return the payload of a valid token of the expected scope, else raise 401."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise credentials_exception

    if payload.get("scope") != expected_scope or payload.get("sub") is None:
        raise credentials_exception
    return payload


# ---------- dependencies ----------

def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    """Current user from Redis cache, falling back to the database.

    The cached user is detached from the session: routes that modify the user
    must reload it with ``repository_users.get_user_by_email``.
    """
    email = decode_token(token, ACCESS_SCOPE)
    user = cache.get_cached_user(email)
    if user is not None:
        return user
    user = repository_users.get_user_by_email(email, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    cache.cache_user(user)
    return user


def get_refresh_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(refresh_scheme),
) -> str:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials
