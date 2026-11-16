"""Tâche 41: a phone only lists and scans the units / zones / posts it was given."""

from tests.test_units_devices_agents import _pair


def site(client, admin, world):
    """Second unit with a zone and a post, besides the « Usine » zone of the world fixture."""
    unit = client.post("/api/units", headers=admin, json={"name": "Siège Akwa"}).json()
    bureaux = client.post("/api/zones", headers=admin, json={"name": "Bureaux", "unit_id": unit["id"]}).json()
    accueil = client.post(
        f"/api/zones/{bureaux['id']}/checkpoints", headers=admin, json={"name": "Accueil", "direction": "ENTREE"}
    ).json()
    return unit, bureaux, accueil


def posts(client, device):
    return sorted(c["name"] for c in client.get("/api/device/checkpoints", headers=device).json())


def scope(client, admin, device_id, **ids):
    response = client.put(f"/api/devices/{device_id}/scope", headers=admin, json=ids)
    assert response.status_code == 200, response.text
    return response.json()


def test_without_perimeter_the_phone_sees_the_whole_site(client, admin, world):
    site(client, admin, world)
    device_id, device = _pair(client, admin)
    assert posts(client, device) == ["Accueil", "Entrée usine", "Sortie usine"]
    listed = next(d for d in client.get("/api/devices", headers=admin).json() if d["id"] == device_id)
    assert listed["scope_summary"] == "Tout le site"


def test_phone_lists_and_scans_only_its_perimeter(client, admin, world):
    _, _, accueil = site(client, admin, world)
    device_id, device = _pair(client, admin)
    out = scope(client, admin, device_id, zone_ids=[world["zone"]["id"]])
    assert out["scope_summary"] == "Usine (toute la zone)"
    assert posts(client, device) == ["Entrée usine", "Sortie usine"]
    ok = client.post(
        "/api/device/scan", headers=device, json={"checkpoint_id": world["entry"]["id"], "token": world["token"]}
    )
    assert ok.json()["verdict"] == "AUTORISE"
    refused = client.post(
        "/api/device/scan", headers=device, json={"checkpoint_id": accueil["id"], "token": world["token"]}
    )
    assert refused.status_code == 403 and "périmètre" in refused.json()["detail"]
    manual = client.post(
        "/api/device/scan/manual", headers=device, json={"checkpoint_id": accueil["id"], "matricule": "EMP-0042"}
    )
    assert manual.status_code == 403


def test_unit_scope_includes_posts_created_later_and_single_posts(client, admin, world):
    unit, bureaux, accueil = site(client, admin, world)
    device_id, device = _pair(client, admin)
    scope(client, admin, device_id, unit_ids=[unit["id"]], checkpoint_ids=[world["exit"]["id"]])
    assert posts(client, device) == ["Accueil", "Sortie usine"]
    client.post(
        f"/api/zones/{bureaux['id']}/checkpoints", headers=admin, json={"name": "Sortie accueil", "direction": "SORTIE"}
    )
    assert posts(client, device) == ["Accueil", "Sortie accueil", "Sortie usine"]


def test_what_a_ticked_unit_contains_is_not_stored_twice(client, admin, world):
    unit, bureaux, accueil = site(client, admin, world)
    device_id, _ = _pair(client, admin)
    out = scope(
        client, admin, device_id, unit_ids=[unit["id"]], zone_ids=[bureaux["id"]], checkpoint_ids=[accueil["id"]]
    )
    assert out["scope_ids"] == {"unit_ids": [unit["id"]], "zone_ids": [], "checkpoint_ids": []}
    assert out["scope_summary"] == "Siège Akwa (toute l'unité)"


def test_back_to_whole_site_rights_audit_and_unknown_ids(client, admin, agent, world):
    device_id, device = _pair(client, admin)
    scope(client, admin, device_id, checkpoint_ids=[world["entry"]["id"]])
    assert posts(client, device) == ["Entrée usine"]
    assert scope(client, admin, device_id)["scope_summary"] == "Tout le site"
    assert posts(client, device) == ["Entrée usine", "Sortie usine"]
    assert client.put(f"/api/devices/{device_id}/scope", headers=agent, json={}).status_code == 403
    assert client.put(f"/api/devices/{device_id}/scope", headers=admin, json={"zone_ids": [999]}).status_code == 404
    line = client.get("/api/audit?action=device.scope", headers=admin).json()[0]
    assert line["summary"] == "Périmètre : Entrée usine · Usine → Tout le site"
