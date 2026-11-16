"""Passwords (tâche 14): change one's own, admin reset, forced change, old sessions closed."""


def login(client, username, password):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def bearer(response):
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def change(client, headers, current, new):
    return client.post("/api/auth/password", headers=headers, json={"current_password": current, "new_password": new})


def create(client, admin, username="rh2", password="Temp-2026a"):
    role = next(r["id"] for r in client.get("/api/roles", headers=admin).json() if r["name"] == "rh")
    response = client.post("/api/users", headers=admin, json={"username": username, "full_name": "RH Deux",
                                                               "password": password, "role_id": role})
    assert response.status_code == 201, response.text
    return response.json()


def test_new_account_must_change_its_temporary_password(client, admin):
    created = create(client, admin)
    assert created["must_change_password"] is True
    temp = bearer(login(client, "rh2", "Temp-2026a"))
    assert client.get("/api/auth/me", headers=temp).json()["must_change_password"] is True
    blocked = client.get("/api/employees", headers=temp)
    assert blocked.status_code == 403 and "mot de passe" in blocked.json()["detail"]

    fresh = bearer(change(client, temp, "Temp-2026a", "Nouveau-2026"))
    assert client.get("/api/auth/me", headers=fresh).json()["must_change_password"] is False
    assert client.get("/api/employees", headers=fresh).status_code == 200
    assert login(client, "rh2", "Temp-2026a").status_code == 401
    assert login(client, "rh2", "Nouveau-2026").status_code == 200


def test_change_closes_the_other_sessions(client, admin, clock):
    create(client, admin)
    temp = bearer(login(client, "rh2", "Temp-2026a"))
    clock.advance(seconds=5)
    fresh = bearer(change(client, temp, "Temp-2026a", "Nouveau-2026"))
    assert client.get("/api/auth/me", headers=temp).status_code == 401  # old session dead
    assert client.get("/api/auth/me", headers=fresh).status_code == 200


def test_change_checks_current_password_and_rules(client, admin):
    create(client, admin)
    temp = bearer(login(client, "rh2", "Temp-2026a"))
    assert change(client, temp, "wrong", "Nouveau-2026").status_code == 400
    assert change(client, temp, "Temp-2026a", "Temp-2026a").status_code == 400  # same as before
    assert change(client, temp, "Temp-2026a", "seulementdeslettres").status_code == 400  # no digit
    assert change(client, temp, "Temp-2026a", "court1").status_code == 422  # too short


def test_password_cannot_be_the_username(client, admin):
    create(client, admin, username="paul2026", password="Temp-2026a")
    temp = bearer(login(client, "paul2026", "Temp-2026a"))
    response = change(client, temp, "Temp-2026a", "PAUL2026")
    assert response.status_code == 400 and "identifiant" in response.json()["detail"]


def test_admin_reset_forces_a_change_and_closes_sessions(client, admin, clock):
    created = create(client, admin)
    fresh = bearer(change(client, bearer(login(client, "rh2", "Temp-2026a")), "Temp-2026a", "Nouveau-2026"))
    clock.advance(seconds=5)
    reset = client.post(f"/api/users/{created['id']}/password", headers=admin, json={"new_password": "Reset-2026b"})
    assert reset.status_code == 200 and reset.json()["must_change_password"] is True
    assert client.get("/api/auth/me", headers=fresh).status_code == 401
    temp = bearer(login(client, "rh2", "Reset-2026b"))
    assert client.get("/api/employees", headers=temp).status_code == 403
    actions = [a["action"] for a in client.get("/api/audit?limit=500", headers=admin).json()]
    assert {"user.password.change", "user.password.reset"} <= set(actions)


def test_reset_rules(client, admin, make_user):
    created = create(client, admin)
    me = next(u["id"] for u in client.get("/api/users", headers=admin).json() if u["username"] == "admin")
    own = client.post(f"/api/users/{me}/password", headers=admin, json={"new_password": "Reset-2026b"})
    assert own.status_code == 403
    su = make_user("su", "super_user")  # no users.manage
    response = client.post(f"/api/users/{created['id']}/password", headers=su, json={"new_password": "Reset-2026b"})
    assert response.status_code == 403
    weak = client.post(f"/api/users/{created['id']}/password", headers=admin, json={"new_password": "abcdefgh"})
    assert weak.status_code == 400


def test_installation_admin_must_change_its_password(tmp_path, clock):
    from fastapi.testclient import TestClient

    from app.core.config import Settings
    from app.main import create_app

    settings = Settings(database_url="sqlite://", jwt_secret="x" * 40, initial_admin_password="Install-2026",
                        photos_dir=str(tmp_path / "p"), qr_dev_key_path=str(tmp_path / "k.pem"))
    client = TestClient(create_app(settings, clock))
    headers = bearer(login(client, "admin", "Install-2026"))
    assert client.get("/api/auth/me", headers=headers).json()["must_change_password"] is True
    assert client.get("/api/users", headers=headers).status_code == 403
