"""Tâche 25: « Signalé » mode warns the agent when the zone asks for it; « Déjà entré » shows when."""


def scan(client, headers, checkpoint, token):
    return client.post("/api/scan", headers=headers, json={"checkpoint_id": checkpoint["id"], "token": token}).json()


def set_mode(client, admin, world, mode, warn=None):
    body = {"antipassback_mode": mode}
    if warn is not None:
        body["antipassback_warn_agent"] = warn
    response = client.patch(f"/api/zones/{world['zone']['id']}/antipassback", headers=admin, json=body)
    assert response.status_code == 200, response.text
    return response.json()


def test_double_entry_is_silent_for_the_agent_by_default(client, agent, admin, world):
    set_mode(client, admin, world, "SOUPLE")
    scan(client, agent, world["entry"], world["token"])
    second = scan(client, agent, world["entry"], world["token"])
    assert second["verdict"] == "AUTORISE" and "DOUBLE_ENTREE" in second["flags"]  # journal / reports
    assert second["warning"] is None and second["last_entry_at"] is None


def test_zone_option_warns_the_agent_with_the_last_entry(client, agent, admin, world, clock):
    zone = set_mode(client, admin, world, "SOUPLE", warn=True)
    assert zone["antipassback_warn_agent"] is True
    first = scan(client, agent, world["entry"], world["token"])
    clock.advance(minutes=40)
    second = scan(client, agent, world["entry"], world["token"])
    assert second["verdict"] == "AUTORISE" and second["warning"] == "DOUBLE_ENTREE"
    assert second["last_entry_at"] == first["occurred_at"] and second["last_entry_checkpoint"] == "Entrée usine"


def test_already_inside_in_strict_mode_shows_when_the_person_entered(client, agent, admin, world):
    first = scan(client, agent, world["entry"], world["token"])
    refused = scan(client, agent, world["entry"], world["token"])
    assert refused["verdict"] == "REFUSE_ANTIPASSBACK"
    assert refused["last_entry_at"] == first["occurred_at"] and refused["last_entry_checkpoint"] == "Entrée usine"
    assert refused["warning"] is None


def test_warning_option_only_lives_in_signale_mode(client, admin, world):
    set_mode(client, admin, world, "SOUPLE", warn=True)
    assert set_mode(client, admin, world, "SOUPLE")["antipassback_warn_agent"] is True  # omitted -> unchanged
    assert set_mode(client, admin, world, "STRICT", warn=True)["antipassback_warn_agent"] is False
    created = client.post("/api/zones", headers=admin, json={
        "name": "Quai", "antipassback_mode": "SOUPLE", "antipassback_warn_agent": True}).json()
    assert created["antipassback_warn_agent"] is True
    line = client.get("/api/audit?action=zone.antipassback", headers=admin).json()[0]
    assert {c["field"] for c in line["changes"]} == {"mode", "warn_agent"}
