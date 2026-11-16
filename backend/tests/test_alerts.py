"""Tâches 27-28: suspicious badge use raises alerts (FR-90 to FR-93); the verdict never changes."""


def scan(client, headers, checkpoint, token):
    return client.post("/api/scan", headers=headers, json={"checkpoint_id": checkpoint["id"], "token": token}).json()


def alerts(client, admin, **query):
    params = "&".join(f"{k}={v}" for k, v in query.items())
    response = client.get(f"/api/alerts?{params}", headers=admin)
    assert response.status_code == 200, response.text
    return response.json()


def other_site(client, admin, world):
    """A post in another unit, where the employee is also allowed."""
    unit = client.post("/api/units", headers=admin, json={"name": "Siège Akwa"}).json()
    zone = client.post("/api/zones", headers=admin, json={"name": "Bureaux", "unit_id": unit["id"]}).json()
    post = client.post(f"/api/zones/{zone['id']}/checkpoints", headers=admin,
                       json={"name": "Accueil", "direction": "ENTREE"}).json()
    client.put(f"/api/employees/{world['employee']['id']}/access", headers=admin,
               json={"zone_ids": [world["zone"]["id"], zone["id"]]})
    return post


def test_revoked_badge_presented_raises_an_alert_each_time(client, agent, admin, world):
    client.post(f"/api/badges/{world['badge']['id']}/revoke", headers=admin, json={"reason": "VOL"})
    assert scan(client, agent, world["entry"], world["token"])["verdict"] == "REFUSE_REVOQUE"
    scan(client, agent, world["entry"], world["token"])
    found = alerts(client, admin, type="BADGE_REVOQUE")
    assert len(found) == 2 and found[0]["status"] == "NOUVELLE"
    assert found[0]["employee_matricule"] == "EMP-0042" and found[0]["checkpoint_name"] == "Entrée usine"
    assert client.get("/api/alerts/count", headers=admin).json() == {"new": 2}


def test_archived_employee_qr_raises_an_alert(client, agent, admin, world):
    client.post(f"/api/employees/{world['employee']['id']}/archive", headers=admin, json={"reason": "Départ"})
    assert scan(client, agent, world["entry"], world["token"])["verdict"] == "REFUSE_INVALIDE"
    (alert,) = alerts(client, admin, type="EMPLOYE_ARCHIVE")
    assert alert["employee_matricule"] == "EMP-0042" and alert["badge_id"] == world["badge"]["id"]


def test_same_badge_at_two_sites_too_fast(client, agent, admin, world, clock):
    accueil = other_site(client, admin, world)
    scan(client, agent, world["entry"], world["token"])
    clock.advance(seconds=40)
    second = scan(client, agent, accueil, world["token"])
    assert second["verdict"] == "AUTORISE"  # a signal, not a refusal
    (alert,) = alerts(client, admin, type="SIMULTANEE")
    assert "« Entrée usine » puis à « Accueil » en 40 s" in alert["message"] and "10 min" in alert["message"]
    assert alert["detail"]["elapsed_seconds"] == 40 and alert["detail"]["required_seconds"] == 600


def test_travel_time_per_pair_overrides_the_default(client, agent, admin, world, clock):
    accueil = other_site(client, admin, world)
    pair = {"checkpoint_a_id": accueil["id"], "checkpoint_b_id": world["entry"]["id"], "minutes": 0}
    assert client.put("/api/travel-times", headers=admin, json=pair).status_code == 200  # 0 = no check
    scan(client, agent, world["entry"], world["token"])
    clock.advance(seconds=30)
    scan(client, agent, accueil, world["token"])
    assert alerts(client, admin, type="SIMULTANEE") == []
    # Inside one unit there is no check by default... unless a time is set for the pair.
    exit_pair = {"checkpoint_a_id": world["entry"]["id"], "checkpoint_b_id": world["exit"]["id"], "minutes": 2}
    saved = client.put("/api/travel-times", headers=admin, json=exit_pair).json()
    assert saved["min_seconds"] == 120 and {saved["checkpoint_a_name"], saved["checkpoint_b_name"]} == {
        "Entrée usine", "Sortie usine"}
    clock.advance(minutes=5)
    scan(client, agent, world["entry"], world["token"])
    clock.advance(seconds=20)
    scan(client, agent, world["exit"], world["token"])
    assert len(alerts(client, admin, type="SIMULTANEE")) == 1
    assert len(client.get("/api/travel-times", headers=admin).json()) == 2


def test_burst_of_scans_is_reported_once(client, agent, admin, world, clock):
    for _ in range(7):
        scan(client, agent, world["entry"], world["token"])
        clock.advance(seconds=5)
    (alert,) = alerts(client, admin, type="RAFALE")
    assert alert["message"].startswith("5 scans du même badge")


def test_repeated_refusals(client, agent, admin, world, clock):
    client.put(f"/api/employees/{world['employee']['id']}/access", headers=admin, json={"zone_ids": []})
    for _ in range(3):
        assert scan(client, agent, world["entry"], world["token"])["verdict"] == "REFUSE_ZONE"
        clock.advance(minutes=1)
    (alert,) = alerts(client, admin, type="REFUS_REPETES")
    assert alert["detail"]["refusals"] == 3


def test_outside_hours_attempt(client, agent, admin, world):
    url = f"/api/employees/{world['employee']['id']}/access/{world['zone']['id']}/restrictions"
    client.put(url, headers=admin, json={"schedules": [{"weekdays": [6], "start": "08:00", "end": "12:00"}]})
    scan(client, agent, world["entry"], world["token"])
    assert len(alerts(client, admin, type="HORS_HORAIRE")) == 1


def test_acknowledge_and_revoke_from_the_alert(client, agent, admin, world, clock, make_user):
    accueil = other_site(client, admin, world)
    scan(client, agent, world["entry"], world["token"])
    clock.advance(seconds=10)
    scan(client, agent, accueil, world["token"])
    (alert,) = alerts(client, admin, type="SIMULTANEE")
    assert client.get("/api/alerts", headers=agent).status_code == 403
    done = client.post(f"/api/alerts/{alert['id']}/revoke-badge", headers=admin,
                       json={"reason": "AUTRE", "note": "Badge copié"}).json()
    assert done["status"] == "PRISE_EN_COMPTE" and done["note"] == "Badge révoqué : Badge copié"
    badges = client.get(f"/api/employees/{world['employee']['id']}/badges", headers=admin).json()
    assert badges[0]["status"] == "REVOQUE" and badges[0]["revoked_reason"] == "AUTRE"
    assert client.post(f"/api/alerts/{alert['id']}/ack", headers=admin, json={}).status_code == 409
    assert all(a["id"] != alert["id"] for a in alerts(client, admin, status="NOUVELLE"))
    actions = [a["action"] for a in client.get("/api/audit?limit=50", headers=admin).json()]
    assert "alert.ack" in actions and "badge.revoke" in actions
