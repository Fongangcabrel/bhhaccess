"""Edit / delete units, zones, posts, phones and agents (tâche 7).

Rule: what the journal or the agents' history refers to is deactivated, never deleted.
"""


def make_zone(client, admin, name="Atelier", **extra):
    response = client.post("/api/zones", headers=admin, json={"name": name, **extra})
    assert response.status_code == 201, response.text
    return response.json()


def make_post(client, admin, zone, name="Porte A", direction="ENTREE"):
    return client.post(f"/api/zones/{zone['id']}/checkpoints", headers=admin,
                       json={"name": name, "direction": direction}).json()


def actions(client, admin):
    return [a["action"] for a in client.get("/api/audit?limit=500", headers=admin).json()]


# --- units -------------------------------------------------------------------
def test_rename_and_delete_unit(client, admin):
    unit = client.post("/api/units", headers=admin, json={"name": "Usine"}).json()
    other = client.post("/api/units", headers=admin, json={"name": "Siège"}).json()
    assert client.patch(f"/api/units/{unit['id']}", headers=admin, json={"name": "Siège"}).status_code == 409
    renamed = client.patch(f"/api/units/{unit['id']}", headers=admin, json={"name": "Usine de Bonabéri"})
    assert renamed.status_code == 200 and renamed.json()["name"] == "Usine de Bonabéri"

    make_zone(client, admin, unit_id=other["id"])
    assert client.delete(f"/api/units/{other['id']}", headers=admin).status_code == 409  # still has zones
    assert client.delete(f"/api/units/{unit['id']}", headers=admin).status_code == 204
    assert {"unit.rename", "unit.delete"} <= set(actions(client, admin))


# --- zones -------------------------------------------------------------------
def test_create_and_edit_zone_details(client, admin):
    zone = make_zone(client, admin, code="dc-01", sensitivity="CRITIQUE", description="Salle serveurs")
    assert zone["code"] == "DC-01" and zone["sensitivity"] == "CRITIQUE" and zone["is_active"] is True
    make_zone(client, admin, "Parking", code="PK-01")
    url = f"/api/zones/{zone['id']}"
    assert client.patch(url, headers=admin, json={"code": "pk-01"}).status_code == 409
    assert client.patch(url, headers=admin, json={"name": "Parking"}).status_code == 409
    edited = client.patch(url, headers=admin, json={"name": "Data center", "description": None,
                                                    "sensitivity": "RESTREINTE"}).json()
    assert edited["name"] == "Data center" and edited["description"] is None
    assert edited["sensitivity"] == "RESTREINTE" and edited["antipassback_mode"] == "DESACTIVE"
    audit = next(a for a in client.get("/api/audit?limit=500", headers=admin).json() if a["action"] == "zone.update")
    assert audit["detail"]["before"]["sensitivity"] == "CRITIQUE"


def test_unused_zone_is_deleted_with_its_posts_and_authorisations(client, admin):
    zone = make_zone(client, admin)
    make_post(client, admin, zone)
    employee = client.post("/api/employees", headers=admin,
                           json={"matricule": "E1", "last_name": "A", "first_name": "B"}).json()
    client.put(f"/api/employees/{employee['id']}/access", headers=admin, json={"zone_ids": [zone["id"]]})
    assert client.delete(f"/api/zones/{zone['id']}", headers=admin).status_code == 204
    assert client.get("/api/checkpoints", headers=admin).json() == []
    assert client.get(f"/api/employees/{employee['id']}/authorizations", headers=admin).json() == []


def test_zone_with_history_is_deactivated_not_deleted(client, agent, admin, world):
    client.post("/api/scan", headers=agent, json={"checkpoint_id": world["entry"]["id"], "token": world["token"]})
    zone_url = f"/api/zones/{world['zone']['id']}"
    response = client.delete(zone_url, headers=admin)
    assert response.status_code == 409 and "désactivez" in response.json()["detail"]

    assert client.patch(zone_url, headers=admin, json={"is_active": False}).json()["is_active"] is False
    body = {"checkpoint_id": world["entry"]["id"], "token": world["token"]}
    scan = client.post("/api/scan", headers=agent, json=body)
    assert scan.status_code == 409  # its posts can no longer scan
    posts = {c["id"]: c for c in client.get("/api/checkpoints", headers=admin).json()}
    assert posts[world["entry"]["id"]]["usable"] is False
    assert len(client.get("/api/logs", headers=admin).json()) == 1  # history intact


# --- checkpoints -------------------------------------------------------------
def test_edit_deactivate_and_delete_post(client, agent, admin, world):
    post = make_post(client, admin, world["zone"], "Porte de service", "SORTIE")
    url = f"/api/checkpoints/{post['id']}"
    edited = client.patch(url, headers=admin, json={"name": "Porte quai", "direction": "ENTREE"}).json()
    assert edited["name"] == "Porte quai" and edited["direction"] == "ENTREE"
    assert client.delete(url, headers=admin).status_code == 204

    client.post("/api/scan", headers=agent, json={"checkpoint_id": world["entry"]["id"], "token": world["token"]})
    used = f"/api/checkpoints/{world['entry']['id']}"
    assert client.delete(used, headers=admin).status_code == 409
    assert client.patch(used, headers=admin, json={"is_active": False}).json()["is_active"] is False
    body = {"checkpoint_id": world["entry"]["id"], "token": world["token"]}
    scan = client.post("/api/scan", headers=agent, json=body)
    assert scan.status_code == 409


def test_deactivated_post_is_hidden_from_phones(client, admin, world):
    code = client.post("/api/devices", headers=admin, json={"name": "Tel"}).json()["code"]
    phone = {"X-Device-Token": client.post("/api/device/pair", json={"code": code}).json()["device_token"]}
    client.patch(f"/api/checkpoints/{world['exit']['id']}", headers=admin, json={"is_active": False})
    ids = {c["id"] for c in client.get("/api/device/checkpoints", headers=phone).json()}
    assert ids == {world["entry"]["id"]}


# --- phones ------------------------------------------------------------------
def test_rename_and_delete_phone(client, admin, world):
    created = client.post("/api/devices", headers=admin, json={"name": "Tel 1"}).json()
    device_id = created["device"]["id"]
    assert client.patch(f"/api/devices/{device_id}", headers=admin, json={"name": "Tel entrée"}).json()["name"] \
        == "Tel entrée"
    assert client.delete(f"/api/devices/{device_id}", headers=admin).status_code == 204

    code = client.post("/api/devices", headers=admin, json={"name": "Tel 2"}).json()["code"]
    paired = client.post("/api/device/pair", json={"code": code}).json()
    client.post("/api/device/scan", headers={"X-Device-Token": paired["device_token"]},
                json={"checkpoint_id": world["entry"]["id"], "token": world["token"]})
    used_id = next(d["id"] for d in client.get("/api/devices", headers=admin).json() if d["name"] == "Tel 2")
    response = client.delete(f"/api/devices/{used_id}", headers=admin)
    assert response.status_code == 409 and "bloquez" in response.json()["detail"]


# --- agents ------------------------------------------------------------------
def test_edit_and_delete_agent(client, admin, world):
    agent = client.post("/api/agents", headers=admin, json={"full_name": "Jean Ekané", "matricule": "AG-1"}).json()
    client.post("/api/agents", headers=admin, json={"full_name": "Marie Ndi", "matricule": "AG-2"})
    url = f"/api/agents/{agent['id']}"
    assert client.patch(url, headers=admin, json={"full_name": "Jean", "matricule": "AG-2"}).status_code == 409
    edited = client.patch(url, headers=admin, json={"full_name": "Jean Ekané Mbia", "matricule": None}).json()
    assert edited["full_name"] == "Jean Ekané Mbia" and edited["matricule"] is None
    assert client.delete(url, headers=admin).status_code == 204

    posted = client.post("/api/agents", headers=admin, json={"full_name": "Paul Etoa"}).json()
    client.put(f"/api/checkpoints/{world['entry']['id']}/agent", headers=admin, json={"agent_id": posted["id"]})
    assert client.delete(f"/api/agents/{posted['id']}", headers=admin).status_code == 409


def test_cannot_post_an_agent_on_a_deactivated_post(client, admin, world):
    agent = client.post("/api/agents", headers=admin, json={"full_name": "Paul Etoa"}).json()
    client.patch(f"/api/checkpoints/{world['entry']['id']}", headers=admin, json={"is_active": False})
    response = client.put(f"/api/checkpoints/{world['entry']['id']}/agent", headers=admin,
                          json={"agent_id": agent["id"]})
    assert response.status_code == 400


def test_setup_changes_need_zones_manage(client, make_user, world):
    rh = make_user("rh1", "rh")
    assert client.patch(f"/api/zones/{world['zone']['id']}", headers=rh, json={"name": "X"}).status_code == 403
    assert client.delete(f"/api/checkpoints/{world['entry']['id']}", headers=rh).status_code == 403
    assert client.delete("/api/units/1", headers=rh).status_code == 403
