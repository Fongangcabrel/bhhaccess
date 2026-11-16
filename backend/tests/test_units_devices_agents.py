"""Units/zones access, phone pairing (no login) and agent-to-post reporting."""

def _unit(client, admin, name):
    return client.post("/api/units", headers=admin, json={"name": name}).json()


def _zone(client, admin, name, unit_id=None):
    return client.post("/api/zones", headers=admin, json={"name": name, "unit_id": unit_id}).json()


def _pair(client, admin, name="Tel Poste 1"):
    created = client.post("/api/devices", headers=admin, json={"name": name}).json()
    paired = client.post("/api/device/pair", json={"code": created["code"]})
    assert paired.status_code == 200, paired.text
    return created["device"]["id"], {"X-Device-Token": paired.json()["device_token"]}


# --- units & per-unit access ------------------------------------------------------------
def test_zone_without_unit_goes_to_default_unit(client, admin):
    zone = _zone(client, admin, "Hall")
    assert zone["unit_name"] == "Général"


def test_employee_access_by_unit_and_refused_label(client, admin):
    u1, u2 = _unit(client, admin, "Usine"), _unit(client, admin, "Siège")
    z1, z2 = _zone(client, admin, "Atelier", u1["id"]), _zone(client, admin, "Bureaux", u2["id"])
    emp = client.post("/api/employees", headers=admin,
                      json={"matricule": "E1", "last_name": "A", "first_name": "B"}).json()

    before = client.get(f"/api/employees/{emp['id']}/access", headers=admin).json()
    assert {u["unit_name"]: u["status"] for u in before} == {"Usine": "REFUSE", "Siège": "REFUSE"}

    after = client.put(f"/api/employees/{emp['id']}/access", headers=admin,
                       json={"zone_ids": [z1["id"]]}).json()
    assert {u["unit_name"]: u["status"] for u in after} == {"Usine": "ACCES", "Siège": "REFUSE"}
    assert [z["granted"] for u in after if u["unit_name"] == "Usine" for z in u["zones"]] == [True]

    # replacing the set removes what is no longer ticked
    again = client.put(f"/api/employees/{emp['id']}/access", headers=admin,
                       json={"zone_ids": [z2["id"]]}).json()
    assert {u["unit_name"]: u["status"] for u in again} == {"Usine": "REFUSE", "Siège": "ACCES"}
    assert client.put(f"/api/employees/{emp['id']}/access", headers=admin,
                      json={"zone_ids": [999]}).status_code == 404


def test_access_by_unit_drives_the_scan_decision(client, admin, world):
    client.put(f"/api/employees/{world['employee']['id']}/access", headers=admin, json={"zone_ids": []})
    _, device = _pair(client, admin)
    result = client.post("/api/device/scan", headers=device,
                         json={"checkpoint_id": world["entry"]["id"], "token": world["token"]})
    assert result.json()["verdict"] == "REFUSE_ZONE"


# --- pairing ------------------------------------------------------------------------------
def test_paired_phone_scans_without_login_and_is_traced(client, admin, world):
    device_id, device = _pair(client, admin)
    scan = client.post("/api/device/scan", headers=device,
                       json={"checkpoint_id": world["entry"]["id"], "token": world["token"]})
    assert scan.status_code == 200 and scan.json()["verdict"] == "AUTORISE"
    log = client.get("/api/logs", headers=admin).json()[0]
    assert log["device_id"] == device_id and log["device_name"] == "Tel Poste 1"
    assert log["operator_id"] is None
    assert len(client.get("/api/device/checkpoints", headers=device).json()) == 2


def test_scan_without_or_with_wrong_device_token_is_refused(client, world):
    body = {"checkpoint_id": world["entry"]["id"], "token": world["token"]}
    assert client.post("/api/device/scan", json=body).status_code == 401
    assert client.post("/api/device/scan", json=body, headers={"X-Device-Token": "nope"}).status_code == 401


def test_pairing_code_is_single_use_and_expires(client, admin, clock):
    created = client.post("/api/devices", headers=admin, json={"name": "T"}).json()
    assert client.post("/api/device/pair", json={"code": created["code"]}).status_code == 200
    assert client.post("/api/device/pair", json={"code": created["code"]}).status_code == 401  # already used

    late = client.post("/api/devices", headers=admin, json={"name": "T2"}).json()
    clock.advance(minutes=16)
    assert client.post("/api/device/pair", json={"code": late["code"]}).status_code == 401


def test_pairing_code_tolerates_lowercase_and_dash(client, admin):
    created = client.post("/api/devices", headers=admin, json={"name": "T"}).json()
    code = created["code"]
    typed = f"{code[:4]}-{code[4:]}".lower()
    assert client.post("/api/device/pair", json={"code": typed}).status_code == 200


def test_revoked_device_stops_working_and_can_be_repaired(client, admin, world):
    device_id, device = _pair(client, admin)
    body = {"checkpoint_id": world["entry"]["id"], "token": world["token"]}
    assert client.post(f"/api/devices/{device_id}/revoke", headers=admin).json()["status"] == "REVOQUE"
    assert client.post("/api/device/scan", headers=device, json=body).status_code == 401

    code = client.post(f"/api/devices/{device_id}/code", headers=admin).json()["code"]
    new = client.post("/api/device/pair", json={"code": code}).json()
    assert client.post("/api/device/scan", headers={"X-Device-Token": new["device_token"]},
                       json=body).status_code == 200
    assert client.post("/api/device/scan", headers=device, json=body).status_code == 401  # old token dead


def test_pairing_attempts_are_rate_limited(client):
    codes = [client.post("/api/device/pair", json={"code": f"BAD{i:05d}"}).status_code for i in range(10)]
    assert codes[:8] == [401] * 8 and codes[8:] == [429, 429]


def test_device_management_needs_permission(client, agent):
    assert client.post("/api/devices", headers=agent, json={"name": "x"}).status_code == 403


def test_device_token_is_not_stored_in_clear(app, client, admin):
    from app.models import Device
    created = client.post("/api/devices", headers=admin, json={"name": "T"}).json()
    token = client.post("/api/device/pair", json={"code": created["code"]}).json()["device_token"]
    with app.state.session_factory() as session:
        device = session.query(Device).one()
        assert token not in (device.token_hash or "") and created["code"] not in (device.code_hash or "")
        assert device.status == "APPAIRE"


# --- agents at posts ----------------------------------------------------------------------
def test_scan_records_the_agent_posted_at_that_moment(client, admin, world, clock):
    a1 = client.post("/api/agents", headers=admin, json={"full_name": "Jean Mbarga"}).json()
    a2 = client.post("/api/agents", headers=admin, json={"full_name": "Aïcha Bello"}).json()
    entry = world["entry"]["id"]
    _, device = _pair(client, admin)
    body = {"checkpoint_id": entry, "token": world["token"]}

    client.post("/api/device/scan", headers=device, json=body)  # nobody posted yet
    client.put(f"/api/checkpoints/{entry}/agent", headers=admin, json={"agent_id": a1["id"]})
    clock.advance(minutes=1)
    client.post("/api/device/scan", headers=device, json=body)
    client.put(f"/api/checkpoints/{entry}/agent", headers=admin, json={"agent_id": a2["id"]})
    clock.advance(minutes=1)
    client.post("/api/device/scan", headers=device, json=body)

    logs = client.get("/api/logs", headers=admin).json()  # newest first
    assert [log["agent_name"] for log in logs] == ["Aïcha Bello", "Jean Mbarga", None]
    by_agent = client.get(f"/api/logs?agent_id={a1['id']}", headers=admin).json()
    assert len(by_agent) == 1 and by_agent[0]["agent_name"] == "Jean Mbarga"


def test_one_agent_one_post_and_history(client, admin, world, clock):
    a = client.post("/api/agents", headers=admin, json={"full_name": "Jean Mbarga", "matricule": "AG1"}).json()
    entry, exit_ = world["entry"]["id"], world["exit"]["id"]
    client.put(f"/api/checkpoints/{entry}/agent", headers=admin, json={"agent_id": a["id"]})
    clock.advance(hours=4)
    client.put(f"/api/checkpoints/{exit_}/agent", headers=admin, json={"agent_id": a["id"]})

    agents = client.get("/api/agents", headers=admin).json()
    assert agents[0]["checkpoint_name"] == "Sortie usine"
    checkpoints = {c["name"]: c for c in client.get("/api/checkpoints", headers=admin).json()}
    assert checkpoints["Entrée usine"]["agent_name"] is None
    assert checkpoints["Sortie usine"]["agent_name"] == "Jean Mbarga"

    history = client.get(f"/api/assignments?agent_id={a['id']}", headers=admin).json()
    assert [h["checkpoint_name"] for h in history] == ["Sortie usine", "Entrée usine"]
    assert history[0]["ended_at"] is None and history[1]["ended_at"] is not None

    client.put(f"/api/checkpoints/{exit_}/agent", headers=admin, json={"agent_id": None})
    assert client.get("/api/agents", headers=admin).json()[0]["checkpoint_name"] is None


def test_inactive_agent_cannot_be_posted_and_duplicate_matricule_rejected(client, admin, world):
    a = client.post("/api/agents", headers=admin, json={"full_name": "Jean M", "matricule": "AG1"}).json()
    dup = client.post("/api/agents", headers=admin, json={"full_name": "Autre", "matricule": "AG1"})
    assert dup.status_code == 409
    client.patch(f"/api/agents/{a['id']}/active", headers=admin, json={"is_active": False})
    res = client.put(f"/api/checkpoints/{world['entry']['id']}/agent", headers=admin, json={"agent_id": a["id"]})
    assert res.status_code == 400


def test_journal_filters_by_unit_and_csv_has_unit_and_agent(client, admin, clock):
    u1, u2 = _unit(client, admin, "Usine"), _unit(client, admin, "Siège")
    z1, z2 = _zone(client, admin, "Atelier", u1["id"]), _zone(client, admin, "Bureaux", u2["id"])
    c1 = client.post(f"/api/zones/{z1['id']}/checkpoints", headers=admin,
                     json={"name": "P1", "direction": "ENTREE"}).json()
    c2 = client.post(f"/api/zones/{z2['id']}/checkpoints", headers=admin,
                     json={"name": "P2", "direction": "ENTREE"}).json()
    agent = client.post("/api/agents", headers=admin, json={"full_name": "Jean Mbarga"}).json()
    client.put(f"/api/checkpoints/{c1['id']}/agent", headers=admin, json={"agent_id": agent["id"]})
    _, device = _pair(client, admin)
    for c in (c1, c2):
        client.post("/api/device/scan", headers=device, json={"checkpoint_id": c["id"], "token": "garbage"})

    usine = client.get(f"/api/logs?unit_id={u1['id']}", headers=admin).json()
    assert len(usine) == 1 and usine[0]["unit_name"] == "Usine"
    csv_text = client.get("/api/logs/export.csv", headers=admin).text
    assert "Unité;Zone;Point;Agent" in csv_text and "Jean Mbarga" in csv_text


def test_agent_name_snapshot_survives_deactivation(client, admin, world):
    a = client.post("/api/agents", headers=admin, json={"full_name": "Jean Mbarga"}).json()
    client.put(f"/api/checkpoints/{world['entry']['id']}/agent", headers=admin, json={"agent_id": a["id"]})
    _, device = _pair(client, admin)
    client.post("/api/device/scan", headers=device,
                json={"checkpoint_id": world["entry"]["id"], "token": world["token"]})
    client.patch(f"/api/agents/{a['id']}/active", headers=admin, json={"is_active": False})
    assert client.get("/api/logs", headers=admin).json()[0]["agent_name"] == "Jean Mbarga"
