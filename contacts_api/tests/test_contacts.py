from datetime import date, timedelta

from src.repository.contacts import _next_birthday
from tests.conftest import auth_header, register_and_login

CONTACT = {
    "first_name": "John",
    "last_name": "Doe",
    "email": "john@example.com",
    "phone": "+380501234567",
    "birthday": "1990-05-17",
    "additional_info": "friend",
}


def test_contacts_require_auth(client):
    assert client.get("/api/contacts/").status_code == 401
    assert client.post("/api/contacts/", json=CONTACT).status_code == 401
    resp = client.get("/api/contacts/", headers=auth_header("garbage"))
    assert resp.status_code == 401


def test_crud_flow(client):
    h = auth_header(register_and_login(client)["access_token"])

    resp = client.post("/api/contacts/", json=CONTACT, headers=h)
    assert resp.status_code == 201
    cid = resp.json()["id"]

    assert client.get(f"/api/contacts/{cid}", headers=h).json()["email"] == CONTACT["email"]
    assert len(client.get("/api/contacts/", headers=h).json()) == 1
    assert len(client.get("/api/contacts/?first_name=jo", headers=h).json()) == 1
    assert len(client.get("/api/contacts/?last_name=zzz", headers=h).json()) == 0

    resp = client.put(f"/api/contacts/{cid}", json={"phone": "+380990000000"}, headers=h)
    assert resp.status_code == 200
    assert resp.json()["phone"] == "+380990000000"
    assert resp.json()["first_name"] == "John"

    assert client.post("/api/contacts/", json=CONTACT, headers=h).status_code == 409

    assert client.delete(f"/api/contacts/{cid}", headers=h).status_code == 204
    assert client.get(f"/api/contacts/{cid}", headers=h).status_code == 404


def test_users_see_only_their_own_contacts(client):
    alice = auth_header(register_and_login(client, "alice@example.com")["access_token"])
    bob = auth_header(register_and_login(client, "bob@example.com")["access_token"])

    cid = client.post("/api/contacts/", json=CONTACT, headers=alice).json()["id"]

    assert client.get("/api/contacts/", headers=bob).json() == []
    assert client.get(f"/api/contacts/{cid}", headers=bob).status_code == 404
    assert client.put(f"/api/contacts/{cid}", json={"phone": "+111111"}, headers=bob).status_code == 404
    assert client.delete(f"/api/contacts/{cid}", headers=bob).status_code == 404
    # same email is allowed in another user's address book
    assert client.post("/api/contacts/", json=CONTACT, headers=bob).status_code == 201
    assert client.get(f"/api/contacts/{cid}", headers=alice).status_code == 200


def test_upcoming_birthdays(client):
    h = auth_header(register_and_login(client)["access_token"])
    soon = date.today() + timedelta(days=3)
    later = date.today() + timedelta(days=30)
    client.post(
        "/api/contacts/",
        json={**CONTACT, "email": "soon@example.com", "birthday": soon.replace(year=1996).isoformat()},
        headers=h,
    )
    client.post(
        "/api/contacts/",
        json={**CONTACT, "email": "later@example.com", "birthday": later.replace(year=1996).isoformat()},
        headers=h,
    )
    result = client.get("/api/contacts/birthdays", headers=h).json()
    assert [c["email"] for c in result] == ["soon@example.com"]


def test_next_birthday_handles_year_wrap_and_leap_day():
    assert _next_birthday(date(1990, 1, 2), date(2026, 12, 30)) == date(2027, 1, 2)
    assert _next_birthday(date(2000, 2, 29), date(2027, 2, 1)) == date(2027, 3, 1)
    assert _next_birthday(date(2000, 2, 29), date(2028, 2, 1)) == date(2028, 2, 29)
