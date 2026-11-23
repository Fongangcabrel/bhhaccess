"""Live supervision (tâche 12): inside / left by unit and zone, whatever the entry control mode."""


def scan(client, headers, checkpoint, token):
    client.app.state.clock.advance(seconds=4)  # distinct passages: a repeat within 3 s counts once
    response = client.post("/api/scan", headers=headers, json={"checkpoint_id": checkpoint["id"], "token": token})
    assert response.status_code == 200, response.text
    return response.json()


def snapshot(client, admin, query=""):
    response = client.get(f"/api/monitoring{query}", headers=admin)
    assert response.status_code == 200, response.text
    return response.json()


def zone_view(data, name):
    return next(z for u in data["units"] for z in u["zones"] if z["zone_name"] == name)


def free_zone(client, admin, world):
    """A 'Libre' zone (no presence state) with an entry and an exit, the employee authorised."""
    unit = client.post("/api/units", headers=admin, json={"name": "Siège"}).json()
    zone = client.post("/api/zones", headers=admin, json={"name": "Hall", "unit_id": unit["id"]}).json()
    entry = client.post(f"/api/zones/{zone['id']}/checkpoints", headers=admin,
                        json={"name": "Porte hall", "direction": "ENTREE"}).json()
    exit_ = client.post(f"/api/zones/{zone['id']}/checkpoints", headers=admin,
                        json={"name": "Sortie hall", "direction": "SORTIE"}).json()
    client.put("/api/authorizations", headers=admin,
               json={"employee_id": world["employee"]["id"], "zone_id": zone["id"]})
    return unit, zone, entry, exit_


def test_free_zone_inside_then_left_from_the_journal(client, agent, admin, world):
    _, _, entry, exit_ = free_zone(client, admin, world)
    scan(client, agent, entry, world["token"])
    hall = zone_view(snapshot(client, admin), "Hall")
    assert hall["inside"] == 1 and hall["people_inside"][0]["matricule"] == "EMP-0042"
    assert hall["people_inside"][0]["checkpoint_name"] == "Porte hall"

    scan(client, agent, exit_, world["token"])
    data = snapshot(client, admin)
    hall = zone_view(data, "Hall")
    assert hall["inside"] == 0 and hall["exited"] == 1 and hall["people_exited"][0]["full_name"] == "Paul Ngono"
    assert (hall["entries"], hall["exits"]) == (1, 1)
    assert data["totals"]["inside"] == 0 and data["totals"]["exited"] == 1


def test_strict_zone_uses_its_presence_state(client, agent, admin, world):
    scan(client, agent, world["entry"], world["token"])
    usine = zone_view(snapshot(client, admin), "Usine")
    assert usine["mode"] == "STRICT" and usine["inside"] == 1
    payload = {"employee_id": world["employee"]["id"], "zone_id": world["zone"]["id"], "reason": "Sorti sans scan"}
    client.post("/api/presence/unblock", headers=admin, json=payload)
    usine = zone_view(snapshot(client, admin), "Usine")
    assert usine["inside"] == 0 and usine["exited"] == 1


def test_units_add_up_and_can_be_filtered(client, agent, admin, world):
    unit, _, entry, _ = free_zone(client, admin, world)
    scan(client, agent, entry, world["token"])
    scan(client, agent, world["entry"], world["token"])
    data = snapshot(client, admin)
    assert data["totals"]["inside"] == 2 and data["totals"]["entries"] == 2
    siege = next(u for u in data["units"] if u["unit_name"] == "Siège")
    assert siege["inside"] == 1
    only = snapshot(client, admin, f"?unit_id={unit['id']}")
    assert [u["unit_name"] for u in only["units"]] == ["Siège"]
    assert {p["checkpoint_name"] for p in only["posts"]} == {"Porte hall", "Sortie hall"}


def test_refusals_unknown_qr_and_anomalies_are_counted(client, agent, admin, world):
    scan(client, agent, world["entry"], world["token"])
    scan(client, agent, world["entry"], world["token"])  # strict: refused, already inside
    scan(client, agent, world["entry"], "not-a-badge")
    data = snapshot(client, admin)
    assert data["totals"]["refused"] == 2 and data["totals"]["unknown_qr"] == 1
    verdicts = [r["verdict"] for r in data["recent_refusals"]]
    assert verdicts == ["REFUSE_INVALIDE", "REFUSE_ANTIPASSBACK"]  # newest first
    assert data["recent_refusals"][1]["employee_name"] == "Paul Ngono"


def test_posts_show_agent_and_activity(client, agent, admin, world):
    jean = client.post("/api/agents", headers=admin, json={"full_name": "Jean Ekané"}).json()
    client.put(f"/api/checkpoints/{world['entry']['id']}/agent", headers=admin, json={"agent_id": jean["id"]})
    scan(client, agent, world["entry"], world["token"])
    post = next(p for p in snapshot(client, admin)["posts"] if p["checkpoint_name"] == "Entrée usine")
    assert post["agent_name"] == "Jean Ekané" and post["scans_today"] == 1 and post["last_scan"]


def test_archived_people_are_not_listed_inside(client, agent, admin, world):
    _, _, entry, _ = free_zone(client, admin, world)
    scan(client, agent, entry, world["token"])
    client.post(f"/api/employees/{world['employee']['id']}/archive", headers=admin, json={"reason": "Départ"})
    assert snapshot(client, admin)["totals"]["inside"] == 0


def test_yesterday_exits_are_not_today_exits(client, agent, admin, world, clock):
    _, _, entry, exit_ = free_zone(client, admin, world)
    scan(client, agent, entry, world["token"])
    scan(client, agent, exit_, world["token"])
    clock.advance(days=1)
    token = client.post("/api/auth/login", json={"username": "admin", "password": "pw-admin"}).json()["access_token"]
    data = snapshot(client, {"Authorization": f"Bearer {token}"})  # the 8 h session expired meanwhile
    assert data["totals"]["exited"] == 0 and data["totals"]["entries"] == 0


def test_monitoring_needs_logs_view(client, agent):
    assert client.get("/api/monitoring", headers=agent).status_code == 403
