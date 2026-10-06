from html import escape

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from src.conf.config import settings
from src.database.db import get_db
from src.database.models import User
from src.repository import users as repository_users
from src.schemas import (
    MessageResponse,
    RequestEmail,
    ResetPassword,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)
from src.services import auth as auth_service
from src.services import cache
from src.services.email import send_reset_password_email, send_verification_email
from src.services.limiter import limiter

router = APIRouter(prefix="/auth", tags=["auth"])



def AUTH_LIMIT() -> str:
    return settings.rate_limit_auth

INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid email or password",
    headers={"WWW-Authenticate": "Bearer"},
)

# Login accepts both JSON {"email", "password"} and the OAuth2 form
# (username=<email>, password) that Swagger's "Authorize" button sends.
LOGIN_OPENAPI = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["email", "password"],
                    "properties": {
                        "email": {"type": "string", "format": "email"},
                        "password": {"type": "string"},
                    },
                }
            },
            "application/x-www-form-urlencoded": {
                "schema": {
                    "type": "object",
                    "required": ["username", "password"],
                    "properties": {
                        "username": {"type": "string", "description": "email"},
                        "password": {"type": "string"},
                    },
                }
            },
        },
    }
}


async def get_login_credentials(request: Request) -> UserLogin:
    content_type = request.headers.get("content-type", "")
    try:
        if content_type.startswith("application/json"):
            data = await request.json()
        else:
            form = await request.form()
            data = {"email": form.get("username") or form.get("email"), "password": form.get("password")}
        return UserLogin.model_validate(data)
    except ValidationError as e:
        raise RequestValidationError(e.errors(include_url=False))
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed request body")


def send_confirmation(background_tasks: BackgroundTasks, request: Request, user: User) -> None:
    token = auth_service.create_email_token(user.email)
    link = str(request.url_for("confirmed_email", token=token))
    background_tasks.add_task(send_verification_email, user.email, user.username, link)


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(AUTH_LIMIT)
def signup(
    body: UserCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
):
    """Register a user and email a confirmation link. Login works only after confirmation."""
    if repository_users.get_user_by_email(body.email, db):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Account already exists"
        )
    hashed = auth_service.hash_password(body.password)
    user = repository_users.create_user(body, hashed, db)
    send_confirmation(background_tasks, request, user)
    return user


@router.post("/login", response_model=TokenResponse, openapi_extra=LOGIN_OPENAPI)
@limiter.limit(AUTH_LIMIT)
def login(
    request: Request,
    body: UserLogin = Depends(get_login_credentials),
    db: Session = Depends(get_db),
):
    """Log in with email and password; returns an access/refresh token pair."""
    user = repository_users.get_user_by_email(body.email, db)
    # check a dummy hash for unknown emails so the response time does not reveal them
    hashed = user.password if user is not None else auth_service.DUMMY_HASH
    if not auth_service.verify_password(body.password, hashed) or user is None:
        raise INVALID_CREDENTIALS
    if not user.confirmed:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email not confirmed",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = auth_service.create_access_token(user.email)
    refresh_token = auth_service.create_refresh_token(user.email)
    repository_users.update_refresh_token(user, refresh_token, db)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.get("/refresh_token", response_model=TokenResponse)
def refresh_token(
    token: str = Depends(auth_service.get_refresh_token), db: Session = Depends(get_db)
):
    """Exchange a valid refresh token (Authorization: Bearer <refresh_token>) for a new pair."""
    email = auth_service.decode_token(token, auth_service.REFRESH_SCOPE)
    user = repository_users.get_user_by_email(email, db)
    if user is None or user.refresh_token != token:
        if user is not None:
            # token reuse or a stale token: revoke the stored one
            repository_users.update_refresh_token(user, None, db)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = auth_service.create_access_token(user.email)
    new_refresh_token = auth_service.create_refresh_token(user.email)
    repository_users.update_refresh_token(user, new_refresh_token, db)
    return TokenResponse(access_token=access_token, refresh_token=new_refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    current_user: User = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke the stored refresh token; the access token simply expires."""
    user = repository_users.get_user_by_email(current_user.email, db)
    if user is not None:
        repository_users.update_refresh_token(user, None, db)


# ---------- email verification ----------

@router.get("/confirmed_email/{token}", response_model=MessageResponse)
def confirmed_email(token: str, db: Session = Depends(get_db)):
    """Link from the confirmation email."""
    try:
        email = auth_service.decode_token(token, auth_service.EMAIL_SCOPE)
    except HTTPException:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired link")
    user = repository_users.get_user_by_email(email, db)
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification error")
    if user.confirmed:
        return MessageResponse(message="Your email is already confirmed")
    repository_users.confirm_email(user, db)
    cache.invalidate_user(user.email)
    return MessageResponse(message="Email confirmed")


@router.post("/request_email", response_model=MessageResponse)
@limiter.limit(AUTH_LIMIT)
def request_email(
    body: RequestEmail,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
):
    """Send the confirmation link again. The answer does not reveal whether the account exists."""
    user = repository_users.get_user_by_email(body.email, db)
    if user is not None and not user.confirmed:
        send_confirmation(background_tasks, request, user)
    return MessageResponse(message="If the account needs confirmation, check your email")


# ---------- password reset ----------

@router.post("/forgot_password", response_model=MessageResponse)
@limiter.limit(AUTH_LIMIT)
def forgot_password(
    body: RequestEmail,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
):
    """Email a one-time password reset link. The answer does not reveal whether the account exists."""
    user = repository_users.get_user_by_email(body.email, db)
    if user is not None:
        token = auth_service.create_reset_token(user.email, user.password)
        link = str(request.url_for("reset_password_form", token=token))
        background_tasks.add_task(send_reset_password_email, user.email, user.username, link)
    return MessageResponse(message="If the account exists, a password reset link has been sent")


def get_user_for_reset(token: str, db: Session) -> User:
    error = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token"
    )
    try:
        payload = auth_service.decode_token_payload(token, auth_service.RESET_SCOPE)
    except HTTPException:
        raise error
    user = repository_users.get_user_by_email(payload["sub"], db)
    # the token is bound to the old password hash, so it works only once
    if user is None or payload.get("pwd") != auth_service.password_fingerprint(user.password):
        raise error
    return user


@router.post("/reset_password", response_model=MessageResponse)
@limiter.limit(AUTH_LIMIT)
def reset_password(request: Request, body: ResetPassword, db: Session = Depends(get_db)):
    """Set a new password using the token from the email. All sessions are logged out."""
    user = get_user_for_reset(body.token, db)
    repository_users.update_password(user, auth_service.hash_password(body.new_password), db)
    cache.invalidate_user(user.email)
    return MessageResponse(message="Password has been reset")


RESET_FORM = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Reset password</title>
<style>body{{font-family:system-ui,sans-serif;max-width:360px;margin:60px auto;padding:0 16px}}
input,button{{width:100%;padding:8px;margin:6px 0;box-sizing:border-box}}</style></head>
<body><h2>Set a new password</h2>
<form id="f">
<input type="password" id="p1" placeholder="New password" minlength="6" maxlength="64" required>
<input type="password" id="p2" placeholder="Repeat password" required>
<button>Save</button></form>
<p id="msg"></p>
<script>
const form = document.getElementById("f");
form.onsubmit = async (e) => {{
  e.preventDefault();
  const msg = document.getElementById("msg");
  const p1 = document.getElementById("p1").value;
  if (p1 !== document.getElementById("p2").value) {{ msg.textContent = "Passwords do not match"; return; }}
  const r = await fetch("{action}", {{
    method: "POST",
    headers: {{"Content-Type": "application/json"}},
    body: JSON.stringify({{token: "{token}", new_password: p1}}),
  }});
  const data = await r.json();
  msg.textContent = r.ok ? data.message : (typeof data.detail === "string" ? data.detail : "Invalid password");
  if (r.ok) form.remove();
}};
</script></body></html>"""


@router.get("/reset_password/{token}", response_class=HTMLResponse, include_in_schema=False)
def reset_password_form(token: str, request: Request, db: Session = Depends(get_db)):
    """Small HTML page opened from the reset email; it posts to /reset_password."""
    try:
        get_user_for_reset(token, db)
    except HTTPException:
        return HTMLResponse("<h2>The reset link is invalid or has expired.</h2>", status_code=400)
    return RESET_FORM.format(
        action=escape(str(request.url_for("reset_password"))), token=escape(token)
    )