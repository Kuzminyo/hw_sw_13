import cloudinary.exceptions
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from src.database.db import get_db
from src.database.models import User
from src.repository import users as repository_users
from src.schemas import UserResponse
from src.services import cache, upload
from src.services.auth import get_current_user

router = APIRouter(prefix="/users", tags=["users"])

MAX_AVATAR_SIZE = 5 * 1024 * 1024  # 5 MB


@router.get("/me", response_model=UserResponse)
def read_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/avatar", response_model=UserResponse)
def update_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload a new avatar image to Cloudinary and save its URL."""
    if not upload.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Avatar upload is not configured"
        )
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Only image files are allowed"
        )
    if file.size is not None and file.size > MAX_AVATAR_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Image is larger than 5 MB"
        )
    try:
        url = upload.upload_avatar(file.file, current_user.id)
    except cloudinary.exceptions.Error as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Cloudinary error: {e}")

    # the user from get_current_user may come from the cache, so load it from the DB to update
    user = repository_users.get_user_by_email(current_user.email, db)
    user = repository_users.update_avatar(user, url, db)
    cache.invalidate_user(user.email)
    return user