"""Voice at the post: set per phone in the back-office; the scan says which alert it raised."""

from tests.test_units_devices_agents import _pair


def test_voice_is_on_by_default_and_set_per_phone(client, admin, world):
    device_id, device = _pair(client, admin)
    assert client.get("/api/device/settings", headers=device).json()["voice_enabled"] is True
    out = client.put(f"/api/devices/{device_id}/voice", headers=admin, json={"enabled": False})
    assert out.status_code == 200 and out.json()["voice_enabled"] is False
    assert client.get("/api/device/settings", headers=device).json()["voice_enabled"] is False
    assert client.get("/api/device/settings").status_code == 401
    line = client.get("/api/audit?action=device.voice", headers=admin).json()[0]
    assert line["action_label"] == "Voix du téléphone réglée"


def test_scan_reports_the_alert_it_raised(client, admin, world):
    _, device = _pair(client, admin)
    body = {"checkpoint_id": world["entry"]["id"], "token": world["token"]}
    assert client.post("/api/device/scan", headers=device, json=body).json()["alert"] is None
    client.post(f"/api/badges/{world['badge']['id']}/revoke", headers=admin, json={"reason": "VOL"})
    out = client.post("/api/device/scan", headers=device, json=body).json()
    assert out["verdict"] == "REFUSE_REVOQUE" and out["alert"] == "BADGE_REVOQUE"


def test_archived_employee_alert_stays_hidden_from_the_agent(client, admin, world):
    _, device = _pair(client, admin)
    client.post(f"/api/employees/{world['employee']['id']}/archive", headers=admin, json={"reason": "Départ"})
    out = client.post("/api/device/scan", headers=device,
                      json={"checkpoint_id": world["entry"]["id"], "token": world["token"]}).json()
    assert out["verdict"] == "REFUSE_INVALIDE" and out["alert"] is None
