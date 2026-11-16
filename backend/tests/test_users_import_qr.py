"""Users/roles guardrails, Excel import and QR image."""
from io import BytesIO

from openpyxl import Workbook


def role_id(client, headers, name):
    return next(r["id"] for r in client.get("/api/roles", headers=headers).json() if r["name"] == name)


def user_id(client, headers, username):
    return next(u["id"] for u in client.get("/api/users", headers=headers).json() if u["username"] == username)


def new_user(client, admin, username, role):
    body = {"username": username, "full_name": username, "password": "password-1",
            "role_id": role_id(client, admin, role)}
    response = client.post("/api/users", headers=admin, json=body)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def first_login(client, username):
    """Accounts created by an admin start with a temporary password that must be changed."""
    token = client.post("/api/auth/login", json={"username": username, "password": "password-1"}).json()["access_token"]
    changed = client.post("/api/auth/password", headers={"Authorization": f"Bearer {token}"},
                          json={"current_password": "password-1", "new_password": "password-2"})
    assert changed.status_code == 200, changed.text
    return {"Authorization": f"Bearer {changed.json()['access_token']}"}


# --- users & roles --------------------------------------------------------------
def test_only_super_admin_manages_users(client, admin, make_user):
    su = make_user("su", "super_user")
    assert client.get("/api/users", headers=su).status_code == 403
    assert client.get("/api/users", headers=admin).status_code == 200


def test_cannot_edit_own_rights_or_remove_last_super_admin(client, admin):
    me = user_id(client, admin, "admin")
    sa = role_id(client, admin, "super_admin")
    agent = role_id(client, admin, "agent")
    assert client.put(f"/api/users/{me}/role", headers=admin, json={"role_id": agent}).status_code == 403
    assert client.patch(f"/api/users/{me}/active", headers=admin, json={"is_active": False}).status_code == 403
    # a second super admin appears; demoting the first one is then allowed, the last one never
    other = new_user(client, admin, "boss2", "super_admin")
    assert other and sa
    h2 = first_login(client, "boss2")
    assert client.put(f"/api/users/{me}/role", headers=h2, json={"role_id": agent}).status_code == 200
    # boss2 is now the last active super admin: a delegate with users.manage cannot deactivate it
    delegate = new_user(client, h2, "delegate", "super_user")
    client.put(f"/api/users/{delegate}/overrides", headers=h2, json={"permission": "users.manage", "effect": "allow"})
    hd = first_login(client, "delegate")
    response = client.patch(f"/api/users/{other}/active", headers=hd, json={"is_active": False})
    assert response.status_code == 409


def test_override_gives_and_takes_rights_immediately(client, admin):
    agent_id = new_user(client, admin, "agent9", "agent")
    ag = first_login(client, "agent9")
    assert client.get("/api/logs", headers=ag).status_code == 403
    client.put(f"/api/users/{agent_id}/overrides", headers=admin, json={"permission": "logs.view", "effect": "allow"})
    assert client.get("/api/logs", headers=ag).status_code == 200
    client.put(f"/api/users/{agent_id}/overrides", headers=admin, json={"permission": "scan.perform", "effect": "deny"})
    me = client.get("/api/auth/me", headers=ag).json()["permissions"]
    assert "scan.perform" not in me and "logs.view" in me
    client.delete(f"/api/users/{agent_id}/overrides/logs.view", headers=admin)
    assert client.get("/api/logs", headers=ag).status_code == 403


def test_role_bundle_change_propagates_and_is_audited(client, admin):
    agent_id = new_user(client, admin, "agent9", "agent")
    ag = first_login(client, "agent9")
    rid = role_id(client, admin, "agent")
    perms = [*client.get("/api/roles", headers=admin).json()[3]["permissions"], "logs.view"]
    client.put(f"/api/roles/{rid}", headers=admin, json={"permissions": perms})
    assert client.get("/api/logs", headers=ag).status_code == 200
    assert agent_id
    assert any(a["action"] == "role.update" for a in client.get("/api/audit", headers=admin).json())


def test_super_admin_role_is_immutable(client, admin):
    rid = role_id(client, admin, "super_admin")
    assert client.put(f"/api/roles/{rid}", headers=admin, json={"permissions": []}).status_code == 400


# --- Excel import -----------------------------------------------------------------
def workbook(rows):
    wb = Workbook()
    ws = wb.active
    ws.append(["Matricule", "Nom", "Prénom", "Entité", "Département", "Fonction", "Site"])
    for row in rows:
        ws.append(row)
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def upload(client, headers, content, create=False):
    return client.post("/api/employees/import", headers=headers, params={"create_missing_org": create},
                       files={"file": ("emp.xlsx", content,
                                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})


def test_import_creates_only_conforming_rows(client, admin):
    content = workbook([
        ["E1", "Ngono", "Paul", "BHH", "IT", "Dev", "Douala"],
        ["E1", "Doublon", "Jean", "BHH", "IT", "Dev", None],      # duplicate in file
        [None, "SansMatricule", "Zoe", "BHH", "IT", None, None],  # missing matricule
        ["E3", "Inconnu", "Max", "ORG-X", None, None, None],      # unknown entity
    ])
    report = upload(client, admin, content).json()
    assert report["created"] == 0  # entity BHH unknown and creation not requested
    assert len(report["rejected"]) == 4

    report = upload(client, admin, content, create=True).json()
    assert report["created"] == 2  # E1 and E3 (ORG-X created on demand)
    assert {r["row"] for r in report["rejected"]} == {3, 4}
    assert report["created_entities"] == ["BHH", "ORG-X"]
    assert report["created_departments"] == ["IT"]
    employees = client.get("/api/employees", headers=admin, params={"q": "Ngono"}).json()
    assert employees[0]["matricule"] == "E1"


def test_import_rejects_unreadable_file_and_missing_columns(client, admin):
    assert upload(client, admin, b"not excel").status_code == 400
    wb = Workbook()
    wb.active.append(["Nom", "Prénom"])
    buffer = BytesIO()
    wb.save(buffer)
    response = upload(client, admin, buffer.getvalue())
    assert response.status_code == 400 and "matricule" in response.json()["detail"]


def test_import_requires_permission(client, agent):
    assert upload(client, agent, workbook([])).status_code == 403


# --- QR image ---------------------------------------------------------------------
def test_qr_png_is_served(client, admin, world):
    response = client.get(f"/api/badges/{world['badge']['id']}/qr.png", headers=admin)
    assert response.status_code == 200 and response.headers["content-type"] == "image/png"
    assert response.content[:8] == b"\x89PNG\r\n\x1a\n"
