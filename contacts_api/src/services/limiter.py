import jwt
from fastapi import Request, status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from src.conf.config import settings


def user_or_ip_key(request: Request) -> str:
    """Limit per user (email from the bearer token); anonymous requests are limited per IP."""
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() == "bearer" and token:
        try:
            payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
            if payload.get("sub"):
                return f"user:{payload['sub']}"
        except jwt.PyJWTError:
            pass
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(
    key_func=user_or_ip_key,
    storage_uri=settings.rate_limit_storage_uri or settings.redis_url,
    in_memory_fallback_enabled=True,  # keep limiting if Redis goes down
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": f"Too many requests: limit is {exc.detail}"},
    )
