import os

# must be set before the app (and its settings) is imported
os.environ["RATE_LIMIT_STORAGE_URI"] = "memory://"
os.environ["CORS_ORIGINS"] = "http://localhost:3000"

import fakeredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from src.database.db import get_db
from src.database.models import Base, User
from src.routes import auth as auth_routes
from src.services import cache
from src.services.limiter import limiter

engine = create_engine(
    "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
)
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture()
def outbox(monkeypatch):
    """Emails "sent" during the test: list of (kind, email, link)."""
    sent = []
    monkeypatch.setattr(
        auth_routes, "send_verification_email",
        lambda email, username, link: sent.append(("verify", email, link)),
    )
    monkeypatch.setattr(
        auth_routes, "send_reset_password_email",
        lambda email, username, link: sent.append(("reset", email, link)),
    )
    return sent


@pytest.fixture()
def fake_redis(monkeypatch):
    client = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(cache, "redis_client", client)
    return client


@pytest.fixture()
def client(outbox, fake_redis):
    Base.metadata.create_all(bind=engine)
    limiter.reset()

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def confirm_user(email: str) -> None:
    with TestingSession() as db:
        db.execute(update(User).where(User.email == email.lower()).values(confirmed=True))
        db.commit()


def register_and_login(client, email="user@example.com", password="secret123"):
    client.post(
        "/api/auth/signup",
        json={"username": email.split("@")[0], "email": email, "password": password},
    )
    confirm_user(email)
    resp = client.post("/api/auth/login", data={"username": email, "password": password})
    return resp.json()


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}