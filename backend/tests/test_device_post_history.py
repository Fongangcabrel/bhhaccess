"""Tâche 34: the phone shows its last scans (FR-68); each change of post is journalised (FR-33)."""
from tests.conftest import _login
from tests.test_units_devices_agents import _pair


def take(client, device, checkpoint):
    return client.post("/api/device/post", headers=device, json={"checkpoint_id": checkpoint["id"]})


def scan(client, device, checkpoint, token):
    return client.post("/api/device/scan", headers=device, json={"checkpoint_id": checkpoint["id"], "token": token})


def post_changes(client, admin):
    return client.get("/api/audit?action=device.post", headers=admin).json()


def test_each_change_of_post_is_written_in_the_audit_once(client, admin, world):
    device_id, device = _pair(client, admin)
    taken = take(client, device, world["entry"])
    assert taken.status_code == 200
    assert taken.json()["current_post"] == "Entrée usine (entrée) · Usine · Général"
    take(client, device, world["entry"])  # same post again (reload): nothing new
    scan(client, device, world["exit"], world["token"])  # scanning elsewhere = a change of post too

    changes = post_changes(client, admin)
    assert len(changes) == 2
    newest, first = changes
    assert first["target"] == "Tel Poste 1" and first["actor_name"] == "Téléphone / système"
    assert first["action_label"] == "Poste choisi sur le téléphone"
    assert "aucun → Entrée usine (entrée)" in first["summary"]
    assert "Entrée usine (entrée) · Usine · Général → Sortie usine (sortie)" in newest["summary"]
    listed = next(d for d in client.get("/api/devices", headers=admin).json() if d["id"] == device_id)
    assert listed["current_post"].startswith("Sortie usine") and listed["checkpoint_since"]


def test_a_post_outside_the_perimeter_or_deactivated_is_refused(client, admin, world):
    device_id, device = _pair(client, admin)
    client.put(f"/api/devices/{device_id}/scope", headers=admin, json={"checkpoint_ids": [world["entry"]["id"]]})
    assert take(client, device, world["exit"]).status_code == 403
    assert take(client, device, {"id": 9999}).status_code == 404
    client.patch(f"/api/checkpoints/{world['entry']['id']}", headers=admin, json={"is_active": False})
    assert take(client, device, world["entry"]).status_code == 409
    assert post_changes(client, admin) == []


def test_phone_history_shows_its_own_recent_scans_newest_first(client, admin, world, clock):
    _, device = _pair(client, admin)
    _, other = _pair(client, admin, "Tel Poste 2")
    scan(client, device, world["entry"], world["token"])
    clock.advance(minutes=5)
    scan(client, device, world["exit"], world["token"])
    scan(client, other, world["entry"], world["token"])  # another phone: not in this history
    client.post("/api/device/scan", headers=device, json={"checkpoint_id": world["entry"]["id"], "token": "B1FORGED"})

    lines = client.get("/api/device/scans", headers=device).json()
    assert [line["verdict"] for line in lines] == ["REFUSE_INVALIDE", "SORTIE_ENREGISTREE", "AUTORISE"]
    assert lines[1]["employee_name"] == "Paul Ngono" and lines[1]["employee_matricule"] == "EMP-0042"
    assert lines[1]["checkpoint_name"] == "Sortie usine" and "reason" not in lines[1]
    assert len(client.get("/api/device/scans?limit=1", headers=device).json()) == 1

    clock.advance(hours=13)  # the history covers the current shift only
    assert client.get("/api/device/scans", headers=device).json() == []
    assert client.get("/api/device/scans").status_code == 401


def test_archived_person_stays_anonymous_in_the_phone_history(client, admin, world):
    _, device = _pair(client, admin)
    client.post(f"/api/employees/{world['employee']['id']}/archive", headers=admin, json={"reason": "Départ"})
    scan(client, device, world["entry"], world["token"])
    line = client.get("/api/device/scans", headers=device).json()[0]
    assert line["verdict"] == "REFUSE_INVALIDE" and line["employee_name"] is None and line["employee_matricule"] is None
    admin = _login(client, "admin", "pw-admin")
    journal = client.get("/api/logs", headers=admin).json()[0]
    assert journal["employee_name"] == "Paul Ngono"  # the journal keeps who it was
