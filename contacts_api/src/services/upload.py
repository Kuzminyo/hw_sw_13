import cloudinary
import cloudinary.uploader

from src.conf.config import settings


def is_configured() -> bool:
    return bool(settings.cloudinary_name and settings.cloudinary_api_key and settings.cloudinary_api_secret)


def upload_avatar(file, user_id: int) -> str:
    """Upload the image to Cloudinary (overwriting the previous one) and return its URL."""
    cloudinary.config(
        cloud_name=settings.cloudinary_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
        secure=True,
    )
    public_id = f"ContactsApp/user_{user_id}"
    result = cloudinary.uploader.upload(file, public_id=public_id, overwrite=True, invalidate=True)
    return cloudinary.CloudinaryImage(public_id).build_url(
        width=250, height=250, crop="fill", version=result.get("version")
    )
