"""Redis cache of the authenticated user.

Only non-secret fields are cached (no password hash, no refresh token). A cached
user is a detached ``User`` instance: fine for reading ``id``/``email``, but
anything that writes to the user must load it from the database first.
"""
import json
import logging
from datetime import datetime

import redis

from src.conf.config import settings
from src.database.models import User

logger = logging.getLogger(__name__)

CACHED_FIELDS = ("id", "username", "email", "avatar", "confirmed")

redis_client = redis.Redis(
    host=settings.redis_host,
    port=settings.redis_port,
    password=settings.redis_password,
    decode_responses=True,
    socket_connect_timeout=1,
    socket_timeout=1,
)


def _key(email: str) -> str:
    return f"user:{email.lower()}"


def get_cached_user(email: str) -> User | None:
    try:
        raw = redis_client.get(_key(email))
    except redis.RedisError as e:
        logger.warning("Redis unavailable, skipping user cache: %s", e)
        return None
    if raw is None:
        return None
    data = json.loads(raw)
    created_at = data.pop("created_at", None)
    user = User(**data)
    user.created_at = datetime.fromisoformat(created_at) if created_at else None
    return user


def cache_user(user: User) -> None:
    data = {field: getattr(user, field) for field in CACHED_FIELDS}
    data["created_at"] = user.created_at.isoformat() if user.created_at else None
    try:
        redis_client.set(_key(user.email), json.dumps(data), ex=settings.user_cache_ttl_seconds)
    except redis.RedisError as e:
        logger.warning("Redis unavailable, user not cached: %s", e)


def invalidate_user(email: str) -> None:
    try:
        redis_client.delete(_key(email))
    except redis.RedisError as e:
        logger.warning("Redis unavailable, cache not invalidated: %s", e)
