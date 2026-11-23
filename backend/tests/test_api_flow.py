"""End-to-end scenarios through the HTTP API (SQLite in memory, fake clock)."""


def scan(client, agent, checkpoint, token):
    client.app.state.clock.advance(seconds=4)  # distinct passages: a repeat within 3 s counts once
    response = client.post("/api/scan", headers=agent,
                           json={"checkpoint_id": checkpoint["id"], "token": token})
    assert response.status_code == 200, response.text
    return response.json()


def test_login_rejects_bad_password(client):
    response = client.post("/api/auth/login", json={"username": "admin", "password": "nope"})
    assert response.status_code == 401


def test_requires_authentication(client):
    assert client.get("/api/employees").status_code == 401


def test_entry_then_second_entry_blocked_in_strict_zone(client, agent, world):
    first = scan(client, agent, world["entry"], world["token"])
    assert first["verdict"] == "AUTORISE"
    assert first["employee"]["matricule"] == "EMP-0042"
    second = scan(client, agent, world["entry"], world["token"])
    assert second["verdict"] == "REFUSE_ANTIPASSBACK"


def test_exit_frees_the_person(client, agent, world):
    scan(client, agent, world["entry"], world["token"])
    assert scan(client, agent, world["exit"], world["token"])["verdict"] == "SORTIE_ENREGISTREE"
    assert scan(client, agent, world["entry"], world["token"])["verdict"] == "AUTORISE"


def test_supervisor_unblocks_with_mandatory_reason(client, agent, admin, world):
    scan(client, agent, world["entry"], world["token"])
    payload = {"employee_id": world["employee"]["id"], "zone_id": world["zone"]["id"], "reason": "Sorti sans scan"}
    assert client.post("/api/presence/unblock", headers=agent, json=payload).status_code == 403
    assert client.post("/api/presence/unblock", headers=admin, json={**payload, "reason": " "}).status_code == 422
    assert client.post("/api/presence/unblock", headers=admin, json=payload).status_code == 204
    assert scan(client, agent, world["entry"], world["token"])["verdict"] == "AUTORISE"
    actions = [a["action"] for a in client.get("/api/audit", headers=admin).json()]
    assert "presence.unblock" in actions


def test_forged_token_is_logged_as_invalid(client, agent, world):
    assert scan(client, agent, world["entry"], "not.a.token")["verdict"] == "REFUSE_INVALIDE"


def test_revoked_badge_cannot_enter_but_can_leave(client, agent, admin, world):
    scan(client, agent, world["entry"], world["token"])
    client.post(f"/api/badges/{world['badge']['id']}/revoke", headers=admin, json={"reason": "PERTE"})
    assert scan(client, agent, world["entry"], world["token"])["verdict"] == "REFUSE_REVOQUE"
    leave = scan(client, agent, world["exit"], world["token"])
    assert leave["verdict"] == "SORTIE_ENREGISTREE"
    assert "SORTIE_BADGE_REVOQUE" in leave["flags"]


def test_reissue_kills_the_old_qr(client, agent, admin, world):
    client.post("/api/badges", headers=admin, json={"employee_id": world["employee"]["id"]})
    assert scan(client, agent, world["entry"], world["token"])["verdict"] == "REFUSE_REVOQUE"


def test_unauthorised_zone_is_refused(client, agent, admin, world):
    other = client.post("/api/zones", headers=admin, json={"name": "Labo"}).json()
    gate = client.post(f"/api/zones/{other['id']}/checkpoints", headers=admin,
                       json={"name": "Entrée labo", "direction": "ENTREE"}).json()
    assert scan(client, agent, gate, world["token"])["verdict"] == "REFUSE_ZONE"


def test_manual_scan_fallback(client, agent, world):
    response = client.post("/api/scan/manual", headers=agent,
                           json={"checkpoint_id": world["entry"]["id"], "matricule": "EMP-0042"})
    assert response.json()["verdict"] == "AUTORISE"


def test_journal_is_filterable_and_permission_guarded(client, agent, admin, world):
    scan(client, agent, world["entry"], world["token"])
    scan(client, agent, world["entry"], world["token"])
    assert client.get("/api/logs", headers=agent).status_code == 403
    denied = client.get("/api/logs", headers=admin, params={"verdict": "REFUSE_ANTIPASSBACK"}).json()
    assert len(denied) == 1 and denied[0]["checkpoint_id"] == world["entry"]["id"]
    by_zone = client.get("/api/logs", headers=admin, params={"zone_id": world["zone"]["id"]}).json()
    assert len(by_zone) == 2


def test_purge_is_audited_and_rh_may_purge(client, agent, admin, make_user, clock, world):
    scan(client, agent, world["entry"], world["token"])
    clock.advance(hours=1)
    rh = make_user("rh1", "rh")
    body = {"before": clock.now().isoformat()}
    assert client.post("/api/logs/purge", headers=agent, json=body).status_code == 403
    assert client.post("/api/logs/purge", headers=rh, json=body).json()["deleted"] == 1
    assert any(a["action"] == "logs.purge" for a in client.get("/api/audit", headers=admin).json())


def test_super_user_cannot_manage_admin_only_actions(client, make_user):
    me = client.get("/api/auth/me", headers=make_user("su", "super_user")).json()
    assert "data.purge" in me["permissions"] and "users.manage" not in me["permissions"]
