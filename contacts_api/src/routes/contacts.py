from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from src.conf.config import settings
from src.database.db import get_db
from src.database.models import User
from src.repository import contacts as repository_contacts
from src.schemas import ContactCreate, ContactResponse, ContactUpdate
from src.services.auth import get_current_user
from src.services.limiter import limiter

router = APIRouter(prefix="/contacts", tags=["contacts"])

NOT_FOUND = "Contact not found"

# Limits are counted per user (see src/services/limiter.py). `request` is
# required by slowapi in every limited endpoint.
CONTACTS_LIMIT = settings.rate_limit_contacts
CREATE_LIMIT = settings.rate_limit_create_contact


@router.get("/", response_model=list[ContactResponse])
@limiter.limit(CONTACTS_LIMIT)
def read_contacts(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    first_name: str | None = None,
    last_name: str | None = None,
    email: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return repository_contacts.get_contacts(
        db, current_user, skip, limit, first_name, last_name, email
    )


@router.get("/birthdays", response_model=list[ContactResponse])
@limiter.limit(CONTACTS_LIMIT)
def upcoming_birthdays(
    request: Request,
    days: int = Query(7, ge=1, le=366),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return repository_contacts.get_upcoming_birthdays(db, current_user, days)


@router.get("/{contact_id}", response_model=ContactResponse)
@limiter.limit(CONTACTS_LIMIT)
def read_contact(
    request: Request,
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    contact = repository_contacts.get_contact(contact_id, db, current_user)
    if contact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    return contact


@router.post("/", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(CREATE_LIMIT)
def create_contact(
    request: Request,
    body: ContactCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a contact. Limited to RATE_LIMIT_CREATE_CONTACT per user (default 5/minute)."""
    if repository_contacts.get_contact_by_email(body.email, db, current_user):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Contact with this email already exists",
        )
    return repository_contacts.create_contact(body, db, current_user)


@router.put("/{contact_id}", response_model=ContactResponse)
@limiter.limit(CONTACTS_LIMIT)
def update_contact(
    request: Request,
    contact_id: int,
    body: ContactUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    contact = repository_contacts.get_contact(contact_id, db, current_user)
    if contact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    if body.email and body.email != contact.email:
        if repository_contacts.get_contact_by_email(body.email, db, current_user):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Contact with this email already exists",
            )
    return repository_contacts.update_contact(contact, body, db)


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(CONTACTS_LIMIT)
def delete_contact(
    request: Request,
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    contact = repository_contacts.get_contact(contact_id, db, current_user)
    if contact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    repository_contacts.delete_contact(contact, db)