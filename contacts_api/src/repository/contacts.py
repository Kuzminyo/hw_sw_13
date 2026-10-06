from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.models import Contact, User
from src.schemas import ContactCreate, ContactUpdate


def get_contacts(
    db: Session,
    user: User,
    skip: int = 0,
    limit: int = 100,
    first_name: str | None = None,
    last_name: str | None = None,
    email: str | None = None,
) -> list[Contact]:
    stmt = select(Contact).where(Contact.user_id == user.id)
    if first_name:
        stmt = stmt.where(Contact.first_name.ilike(f"%{first_name}%"))
    if last_name:
        stmt = stmt.where(Contact.last_name.ilike(f"%{last_name}%"))
    if email:
        stmt = stmt.where(Contact.email.ilike(f"%{email}%"))
    stmt = stmt.order_by(Contact.id).offset(skip).limit(limit)
    return list(db.scalars(stmt))


def get_contact(contact_id: int, db: Session, user: User) -> Contact | None:
    return db.scalar(
        select(Contact).where(Contact.id == contact_id, Contact.user_id == user.id)
    )


def get_contact_by_email(email: str, db: Session, user: User) -> Contact | None:
    return db.scalar(
        select(Contact).where(Contact.email == email, Contact.user_id == user.id)
    )


def create_contact(body: ContactCreate, db: Session, user: User) -> Contact:
    contact = Contact(**body.model_dump(), user_id=user.id)
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


def update_contact(contact: Contact, body: ContactUpdate, db: Session) -> Contact:
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(contact, field, value)
    db.commit()
    db.refresh(contact)
    return contact


def delete_contact(contact: Contact, db: Session) -> None:
    db.delete(contact)
    db.commit()


def _next_birthday(birthday: date, today: date) -> date:
    def in_year(year: int) -> date:
        try:
            return birthday.replace(year=year)
        except ValueError:  # 29 Feb in a non-leap year
            return date(year, 3, 1)

    upcoming = in_year(today.year)
    if upcoming < today:
        upcoming = in_year(today.year + 1)
    return upcoming


def get_upcoming_birthdays(db: Session, user: User, days: int = 7) -> list[Contact]:
    today = date.today()
    end = today + timedelta(days=days)
    contacts = db.scalars(select(Contact).where(Contact.user_id == user.id))
    result = [c for c in contacts if _next_birthday(c.birthday, today) <= end]
    return sorted(result, key=lambda c: _next_birthday(c.birthday, today))
