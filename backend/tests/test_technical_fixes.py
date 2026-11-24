"""Tâche 40: dates without time zone are refused (422, not 500); stale presences after a mode change."""
import pytest

NAIVE = "2026-11-11T08:00:00"


@pytest.mark.parametrize("path", [
    "/api/logs", "/api/audit", "/api/logs/export.csv", "/api/exports/journal.xlsx", "/api/exports/audit.pdf",
    "/api/reports/movements", "/api/reports/refusals", "/api/exports/presence.xlsx",
])
def test_a_date_without_time_zone_is_refused_cleanly(client, admin, path):
    response = client.get(path, headers=admin, params={"date_from": NAIVE})
    assert response.status_code == 422, response.text
    aware = client.get(path, headers=admin, params={"date_from": NAIVE + "+01:00"})
    assert aware.status_code == 200


def test_naive_dates_in_bodies_are_refused_too(client, admin, world):
    grant = client.put("/api/authorizations", headers=admin, json={
        "employee_id": world["employee"]["id"], "zone_id": world["zone"]["id"], "valid_until": NAIVE})
    assert grant.status_code == 422
    badge = client.post("/api/badges", headers=admin, json={"employee_id": world["employee"]["id"],
                                                             "expires_at": NAIVE})
    assert badge.status_code == 422


def scan(client, agent, checkpoint, token):
    client.app.state.clock.advance(seconds=4)
    return client.post("/api/scan", headers=agent, json={"checkpoint_id": checkpoint["id"], "token": token}).json()


def set_mode(client, admin, zone, mode):
    response = client.patch(f"/api/zones/{zone['id']}/antipassback", headers=admin, json={"antipassback_mode": mode})
    assert response.status_code == 200, response.text


def test_switching_to_free_mode_forgets_presences_that_would_go_stale(client, admin, agent, world):
    assert scan(client, agent, world["entry"], world["token"])["verdict"] == "AUTORISE"  # strict zone: inside
    set_mode(client, admin, world["zone"], "DESACTIVE")
    assert client.get("/api/presence", headers=admin).json() == []
    scan(client, agent, world["exit"], world["token"])  # leaves while exits are not followed
    set_mode(client, admin, world["zone"], "STRICT")
    assert scan(client, agent, world["entry"], world["token"])["verdict"] == "AUTORISE"  # not « déjà entré »

    changes = client.get("/api/audit?action=zone.antipassback", headers=admin).json()
    assert "Présences effacées" in changes[1]["summary"] and "Présences effacées" not in changes[0]["summary"]


def test_strict_and_flagged_modes_keep_presences(client, admin, agent, world):
    scan(client, agent, world["entry"], world["token"])
    set_mode(client, admin, world["zone"], "SOUPLE")
    assert len(client.get("/api/presence", headers=admin).json()) == 1
