"""Tâche 38: session renewal (FR-01), system configuration (system.config), /presence under reports.view."""


def login(client, username="admin", password="pw-admin"):
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def bearer(tokens):
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def refresh(client, token):
    return client.post("/api/auth/refresh", json={"refresh_token": token})


def short_sessions(client, admin, minutes=10, hours=2):
    response = client.patch("/api/settings", headers=admin,
                            json={"values": {"session.access_minutes": minutes, "session.refresh_hours": hours}})
    assert response.status_code == 200, response.text


def test_short_access_token_renewed_with_rotation(client, admin, clock):
    short_sessions(client, admin)
    first = login(client)
    assert first["expires_in"] == 600 and first["refresh_token"]
    clock.advance(minutes=11)
    assert client.get("/api/auth/me", headers=bearer(first)).status_code == 401  # access token expired

    second = refresh(client, first["refresh_token"])
    assert second.status_code == 200
    second = second.json()
    assert second["refresh_token"] != first["refresh_token"]
    assert client.get("/api/auth/me", headers=bearer(second)).json()["username"] == "admin"


def test_a_reused_refresh_token_ends_the_whole_session(client, admin, clock):
    tokens = login(client)
    stolen = tokens["refresh_token"]
    rotated = refresh(client, stolen).json()  # the legitimate user renews
    assert refresh(client, stolen).status_code == 401  # someone replays the copy
    assert refresh(client, rotated["refresh_token"]).status_code == 401  # the session is over for both
    fresh_admin = bearer(login(client))
    assert [a["action"] for a in client.get("/api/audit?action=user.session", headers=fresh_admin).json()] == [
        "user.session.reused"]


def test_session_ends_at_its_fixed_time_whatever_the_renewals(client, admin, clock):
    short_sessions(client, admin, minutes=30, hours=2)
    token = login(client)["refresh_token"]
    for _ in range(3):  # renewed every 25 min: still the same session
        clock.advance(minutes=25)
        token = refresh(client, token).json()["refresh_token"]
    clock.advance(minutes=46)  # 2 h 01 after the login
    expired = refresh(client, token)
    assert expired.status_code == 401 and expired.json()["detail"] == "Session expirée : reconnectez-vous"
    assert refresh(client, "not-a-token").status_code == 401


def test_logout_password_change_and_deactivation_end_sessions(client, admin, make_user):
    tokens = login(client)
    assert client.post("/api/auth/logout", json={"refresh_token": tokens["refresh_token"]}).status_code == 204
    assert refresh(client, tokens["refresh_token"]).status_code == 401

    make_user("rh9", "rh")
    before = login(client, "rh9", "pw")
    changed = client.post("/api/auth/password", headers=bearer(before),
                          json={"current_password": "pw", "new_password": "Nouveau-2026"}).json()
    assert changed["refresh_token"]
    assert refresh(client, before["refresh_token"]).status_code == 401  # opened before the change
    assert refresh(client, changed["refresh_token"]).status_code == 200

    rh_id = next(u["id"] for u in client.get("/api/users", headers=admin).json() if u["username"] == "rh9")
    again = login(client, "rh9", "Nouveau-2026")
    assert client.patch(f"/api/users/{rh_id}/active", headers=admin, json={"is_active": False}).status_code == 200
    assert refresh(client, again["refresh_token"]).status_code == 401


def test_configuration_is_checked_audited_and_reserved(client, admin, make_user):
    rows = {s["key"]: s for s in client.get("/api/settings", headers=admin).json()}
    assert rows["session.refresh_hours"]["value"] == 8 and rows["session.refresh_hours"]["customised"] is False
    assert rows["alerts.burst_count"]["group"] == "Alertes"

    bad = client.patch("/api/settings", headers=admin, json={"values": {"alerts.burst_count": 1}})
    assert bad.status_code == 400 and "Valeur hors limites" in bad.json()["detail"]
    assert client.patch("/api/settings", headers=admin, json={"values": {"x.y": 3}}).status_code == 400
    assert client.get("/api/settings", headers=admin).json()[0]["customised"] is False  # nothing saved

    client.patch("/api/settings", headers=admin, json={"values": {"alerts.burst_count": 4}})
    back = client.patch("/api/settings", headers=admin, json={"values": {"alerts.burst_count": None}}).json()
    assert next(s for s in back if s["key"] == "alerts.burst_count")["customised"] is False
    audit = client.get("/api/audit?action=settings", headers=admin).json()
    assert len(audit) == 2 and "Rafale : nombre de scans" in audit[1]["summary"]

    rh = make_user("rh1", "rh")
    assert client.get("/api/settings", headers=rh).status_code == 403
    assert client.patch("/api/settings", headers=make_user("su1", "super_user"),
                        json={"values": {"alerts.burst_count": 4}}).status_code == 403


def test_alert_thresholds_apply_at_once(client, admin, agent, world, clock):
    client.patch("/api/settings", headers=admin, json={"values": {"alerts.burst_count": 2}})
    for _ in range(2):
        client.post("/api/scan", headers=agent, json={"checkpoint_id": world["entry"]["id"], "token": world["token"]})
        clock.advance(seconds=5)
    assert len(client.get("/api/alerts?type=RAFALE", headers=admin).json()) == 1


def test_presence_needs_reports_view(client, admin, make_user):
    client.post("/api/roles", headers=admin, json={"label": "Journal seul", "permissions": ["logs.view"]})
    assert client.get("/api/presence", headers=make_user("j1", "journal_seul")).status_code == 403
    assert client.get("/api/presence", headers=make_user("rh1", "rh")).status_code == 200
