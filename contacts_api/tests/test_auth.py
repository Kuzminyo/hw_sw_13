import time

from src.database.models import User
from tests.conftest import TestingSession, auth_header, confirm_user, register_and_login

USER = {"username": "alice", "email": "alice@example.com", "password": "secret123"}


def signup_confirmed(client):
    client.post("/api/auth/signup", json=USER)
    confirm_user(USER["email"])


def test_signup_returns_201_and_user_without_password(client):
    resp = client.post("/api/auth/signup", json=USER)
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == USER["email"]
    assert data["username"] == USER["username"]
    assert "password" not in data


def test_password_is_hashed_in_db(client):
    client.post("/api/auth/signup", json=USER)
    with TestingSession() as db:
        user = db.query(User).filter_by(email=USER["email"]).one()
        assert user.password != USER["password"]
        assert user.password.startswith("$2")


def test_signup_duplicate_email_returns_409(client):
    signup_confirmed(client)
    resp = client.post("/api/auth/signup", json={**USER, "username": "other"})
    assert resp.status_code == 409


def test_login_returns_token_pair(client):
    signup_confirmed(client)
    resp = client.post(
        "/api/auth/login", data={"username": USER["email"], "password": USER["password"]}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["access_token"] and data["refresh_token"]
    assert data["token_type"] == "bearer"


def test_login_wrong_password_returns_401(client):
    signup_confirmed(client)
    resp = client.post(
        "/api/auth/login", data={"username": USER["email"], "password": "wrongpass"}
    )
    assert resp.status_code == 401


def test_login_unknown_user_returns_401(client):
    resp = client.post(
        "/api/auth/login", data={"username": "nobody@example.com", "password": "x" * 8}
    )
    assert resp.status_code == 401


def test_refresh_token_issues_new_pair(client):
    tokens = register_and_login(client)
    time.sleep(1)  # make sure iat/exp differ so the new token is not identical
    resp = client.get("/api/auth/refresh_token", headers=auth_header(tokens["refresh_token"]))
    assert resp.status_code == 200
    new = resp.json()
    assert new["refresh_token"] != tokens["refresh_token"]
    # the old refresh token can no longer be used
    resp = client.get("/api/auth/refresh_token", headers=auth_header(tokens["refresh_token"]))
    assert resp.status_code == 401


def test_access_token_cannot_be_used_as_refresh(client):
    tokens = register_and_login(client)
    resp = client.get("/api/auth/refresh_token", headers=auth_header(tokens["access_token"]))
    assert resp.status_code == 401


def test_refresh_token_cannot_access_contacts(client):
    tokens = register_and_login(client)
    resp = client.get("/api/contacts/", headers=auth_header(tokens["refresh_token"]))
    assert resp.status_code == 401


def test_login_accepts_json_body(client):
    signup_confirmed(client)
    resp = client.post(
        "/api/auth/login", json={"email": USER["email"], "password": USER["password"]}
    )
    assert resp.status_code == 200
    assert resp.json()["access_token"]


def test_login_json_wrong_password_returns_401(client):
    signup_confirmed(client)
    resp = client.post("/api/auth/login", json={"email": USER["email"], "password": "nope"})
    assert resp.status_code == 401


def test_login_invalid_body_returns_422(client):
    resp = client.post("/api/auth/login", json={"email": "not-an-email"})
    assert resp.status_code == 422


def test_email_is_case_insensitive(client):
    signup_confirmed(client)
    resp = client.post("/api/auth/signup", json={**USER, "email": "ALICE@example.com"})
    assert resp.status_code == 409
    resp = client.post(
        "/api/auth/login", json={"email": "Alice@Example.com", "password": USER["password"]}
    )
    assert resp.status_code == 200


def test_users_me(client):
    tokens = register_and_login(client)
    resp = client.get("/api/users/me", headers=auth_header(tokens["access_token"]))
    assert resp.status_code == 200
    assert resp.json()["email"] == "user@example.com"
    assert client.get("/api/users/me").status_code == 401


def test_logout_revokes_refresh_token(client):
    tokens = register_and_login(client)
    resp = client.post("/api/auth/logout", headers=auth_header(tokens["access_token"]))
    assert resp.status_code == 204
    resp = client.get("/api/auth/refresh_token", headers=auth_header(tokens["refresh_token"]))
    assert resp.status_code == 401


def test_refresh_without_header_returns_401(client):
    assert client.get("/api/auth/refresh_token").status_code == 401
