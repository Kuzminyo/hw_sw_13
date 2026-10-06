import json

from src.repository import users as repository_users
from src.services import upload
from tests.conftest import auth_header, register_and_login

USER = {"username": "alice", "email": "alice@example.com", "password": "secret123"}
CONTACT = {
    "first_name": "John",
    "last_name": "Doe",
    "email": "john@example.com",
    "phone": "+380501234567",
    "birthday": "1990-05-17",
}


def login(client, password=USER["password"]):
    return client.post("/api/auth/login", json={"email": USER["email"], "password": password})


# ---------- email verification ----------

def test_signup_sends_verification_email_and_login_waits_for_it(client, outbox):
    resp = client.post("/api/auth/signup", json=USER)
    assert resp.status_code == 201
    assert resp.json()["confirmed"] is False
    assert [(kind, email) for kind, email, _ in outbox] == [("verify", USER["email"])]

    resp = login(client)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Email not confirmed"

    link = outbox[0][2]
    resp = client.get(link)
    assert resp.status_code == 200
    assert resp.json()["message"] == "Email confirmed"
    assert login(client).status_code == 200

    assert client.get(link).json()["message"] == "Your email is already confirmed"


def test_confirm_email_rejects_bad_tokens(client):
    assert client.get("/api/auth/confirmed_email/garbage").status_code == 400
    access = register_and_login(client)["access_token"]
    # a token of another scope must not confirm anything
    assert client.get(f"/api/auth/confirmed_email/{access}").status_code == 400


def test_request_email_resends_only_for_unconfirmed(client, outbox):
    client.post("/api/auth/signup", json=USER)
    outbox.clear()
    resp = client.post("/api/auth/request_email", json={"email": USER["email"]})
    assert resp.status_code == 200
    assert len(outbox) == 1

    client.get(outbox[0][2])  # confirm
    outbox.clear()
    other = client.post("/api/auth/request_email", json={"email": USER["email"]})
    unknown = client.post("/api/auth/request_email", json={"email": "nobody@example.com"})
    assert outbox == []
    # same answer, so the endpoint does not reveal which emails are registered
    assert other.json() == unknown.json() == resp.json()


# ---------- rate limiting ----------

def test_create_contact_is_rate_limited_per_user(client):
    alice = auth_header(register_and_login(client, "alice@example.com")["access_token"])
    bob = auth_header(register_and_login(client, "bob@example.com")["access_token"])

    for i in range(5):
        resp = client.post("/api/contacts/", json={**CONTACT, "email": f"c{i}@example.com"}, headers=alice)
        assert resp.status_code == 201
    resp = client.post("/api/contacts/", json={**CONTACT, "email": "c5@example.com"}, headers=alice)
    assert resp.status_code == 429
    assert "Too many requests" in resp.json()["detail"]

    # the limit is per user, bob is not affected
    assert client.post("/api/contacts/", json=CONTACT, headers=bob).status_code == 201


def test_contacts_list_is_rate_limited(client):
    h = auth_header(register_and_login(client)["access_token"])
    codes = [client.get("/api/contacts/", headers=h).status_code for _ in range(31)]
    assert codes[:30] == [200] * 30
    assert codes[30] == 429


# ---------- CORS ----------

def test_cors_allows_configured_origin(client):
    resp = client.options(
        "/api/contacts/",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"},
    )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_rejects_unknown_origin(client):
    resp = client.get("/", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in resp.headers


# ---------- avatar ----------

def test_update_avatar(client, monkeypatch):
    h = auth_header(register_and_login(client)["access_token"])
    client.get("/api/users/me", headers=h)  # put the user into the cache
    url = "https://res.cloudinary.com/demo/image/upload/v1/ContactsApp/user_1"
    calls = []
    monkeypatch.setattr(upload, "is_configured", lambda: True)
    monkeypatch.setattr(upload, "upload_avatar", lambda file, user_id: calls.append(user_id) or url)

    resp = client.patch(
        "/api/users/avatar", headers=h, files={"file": ("me.png", b"\x89PNG fake", "image/png")}
    )
    assert resp.status_code == 200
    assert resp.json()["avatar"] == url
    assert calls == [resp.json()["id"]]
    # cache was invalidated, so /me shows the new avatar
    assert client.get("/api/users/me", headers=h).json()["avatar"] == url


def test_update_avatar_validation(client, monkeypatch):
    h = auth_header(register_and_login(client)["access_token"])
    image = {"file": ("me.png", b"x", "image/png")}

    monkeypatch.setattr(upload, "is_configured", lambda: False)
    assert client.patch("/api/users/avatar", headers=h, files=image).status_code == 503

    monkeypatch.setattr(upload, "is_configured", lambda: True)
    resp = client.patch("/api/users/avatar", headers=h, files={"file": ("a.txt", b"x", "text/plain")})
    assert resp.status_code == 415
    assert client.patch("/api/users/avatar", files=image).status_code == 401


# ---------- Redis cache ----------

def test_current_user_is_cached_in_redis(client, fake_redis, monkeypatch):
    h = auth_header(register_and_login(client)["access_token"])
    assert client.get("/api/users/me", headers=h).status_code == 200

    cached = json.loads(fake_redis.get("user:user@example.com"))
    assert cached["email"] == "user@example.com"
    assert "password" not in cached and "refresh_token" not in cached
    assert fake_redis.ttl("user:user@example.com") > 0

    # the next request is served from the cache without querying the users table
    def fail(*args, **kwargs):
        raise AssertionError("database should not be queried")

    monkeypatch.setattr(repository_users, "get_user_by_email", fail)
    resp = client.get("/api/users/me", headers=h)
    assert resp.status_code == 200
    assert resp.json()["email"] == "user@example.com"


def test_logout_works_with_cached_user(client):
    tokens = register_and_login(client)
    h = auth_header(tokens["access_token"])
    client.get("/api/users/me", headers=h)  # cache it
    assert client.post("/api/auth/logout", headers=h).status_code == 204
    resp = client.get("/api/auth/refresh_token", headers=auth_header(tokens["refresh_token"]))
    assert resp.status_code == 401


# ---------- password reset ----------

def test_password_reset_flow(client, outbox):
    tokens = register_and_login(client, USER["email"], USER["password"])
    outbox.clear()

    resp = client.post("/api/auth/forgot_password", json={"email": USER["email"]})
    assert resp.status_code == 200
    kind, email, link = outbox[0]
    assert (kind, email) == ("reset", USER["email"])

    page = client.get(link)
    assert page.status_code == 200
    assert "Set a new password" in page.text

    token = link.rsplit("/", 1)[1]
    resp = client.post("/api/auth/reset_password", json={"token": token, "new_password": "brand-new-pass"})
    assert resp.status_code == 200

    # old sessions are logged out
    resp = client.get("/api/auth/refresh_token", headers=auth_header(tokens["refresh_token"]))
    assert resp.status_code == 401
    assert login(client).status_code == 401
    assert login(client, "brand-new-pass").status_code == 200
    # the link works only once
    resp = client.post("/api/auth/reset_password", json={"token": token, "new_password": "another-pass"})
    assert resp.status_code == 400
    assert client.get(link).status_code == 400


def test_forgot_password_does_not_reveal_unknown_email(client, outbox):
    register_and_login(client, USER["email"])
    outbox.clear()
    known = client.post("/api/auth/forgot_password", json={"email": USER["email"]})
    unknown = client.post("/api/auth/forgot_password", json={"email": "nobody@example.com"})
    assert known.json() == unknown.json()
    assert len(outbox) == 1


def test_reset_password_rejects_other_tokens(client):
    access = register_and_login(client)["access_token"]
    for token in ("garbage", access):
        resp = client.post("/api/auth/reset_password", json={"token": token, "new_password": "whatever1"})
        assert resp.status_code == 400