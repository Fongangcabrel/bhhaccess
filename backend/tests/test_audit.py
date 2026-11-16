"""Audit (tâche 23): IP, before / after on every change, filters, readable labels, export."""
from io import BytesIO

from openpyxl import load_workbook


def audit(client, admin, query=""):
    response = client.get(f"/api/audit?limit=500{query}", headers=admin)
    assert response.status_code == 200, response.text
    return response.json()


def test_each_line_has_author_name_ip_and_readable_label(client, admin, world):
    first = audit(client, admin, "&action=badge.issue")[0]
    assert first["actor_name"] not in (None, "Téléphone / système")
    assert first["ip"] == "testclient"  # Starlette's test client address
    assert first["action_label"] == "Badge émis" and first["target"] == "EMP-0042"


def test_forwarded_ip_is_used_only_behind_a_trusted_proxy(app, client, admin, world):
    zone = world["zone"]["id"]
    headers = {**admin, "X-Forwarded-For": "10.0.0.7, 172.16.0.1"}
    client.patch(f"/api/zones/{zone}/antipassback", headers=headers, json={"antipassback_mode": "SOUPLE"})
    assert audit(client, admin, "&action=zone.antipassback")[0]["ip"] == "testclient"  # header ignored
    app.state.trust_proxy_headers = True
    client.patch(f"/api/zones/{zone}/antipassback", headers=headers, json={"antipassback_mode": "STRICT"})
    assert audit(client, admin, "&action=zone.antipassback")[0]["ip"] == "10.0.0.7"


def test_changes_carry_before_and_after(client, admin, world):
    zone, employee = world["zone"]["id"], world["employee"]["id"]
    client.patch(f"/api/zones/{zone}/antipassback", headers=admin, json={"antipassback_mode": "SOUPLE"})
    line = audit(client, admin, "&action=zone.antipassback")[0]
    assert line["detail"]["before"] == {"mode": "STRICT", "warn_agent": False}
    assert line["detail"]["after"] == {"mode": "SOUPLE", "warn_agent": False}
    assert line["changes"] == [{"field": "mode", "label": "Contrôle des entrées", "before": "STRICT",
                                "after": "SOUPLE", "before_text": "Sortie obligatoire", "after_text": "Signalé"}]
    assert line["other"] == ""
    assert line["summary"] == "Contrôle des entrées : Sortie obligatoire → Signalé"

    client.patch(f"/api/employees/{employee}/status", headers=admin, json={"status": "SUSPENDU"})
    status = audit(client, admin, "&action=employee.status")[0]
    assert status["summary"] == "Statut : actif → suspendu"

    client.put(f"/api/employees/{employee}/access", headers=admin, json={"zone_ids": []})
    access = audit(client, admin, "&action=authorization.set")[0]
    assert access["detail"]["before"] == {"zones": ["Usine"]} and access["detail"]["after"] == {"zones": []}


def test_user_changes_have_before_and_after(client, admin, make_user):
    make_user("rh1", "rh")
    users = client.get("/api/users", headers=admin).json()
    rh = next(u for u in users if u["username"] == "rh1")
    client.patch(f"/api/users/{rh['id']}/active", headers=admin, json={"is_active": False})
    line = audit(client, admin, "&action=user.deactivate")[0]
    assert line["changes"][0]["before"] is True and line["changes"][0]["after"] is False


def test_filters_by_category_author_object_and_period(client, admin, make_user, world, clock):
    rh_headers = make_user("rh1", "rh")
    client.post("/api/employees", headers=rh_headers, json={"matricule": "EMP-0100", "last_name": "Abena",
                                                             "first_name": "Rose"})
    actors = client.get("/api/audit/actors", headers=admin).json()
    rh = next(a for a in actors if a["name"] == "rh1")
    by_rh = audit(client, admin, f"&actor_id={rh['id']}")
    assert [line["action"] for line in by_rh] == ["employee.create"]
    assert {line["target"] for line in audit(client, admin, "&target=emp-01")} == {"EMP-0100"}
    assert all(line["action"].startswith("badge") for line in audit(client, admin, "&action=badge"))
    def iso(moment):
        return moment.isoformat().replace("+00:00", "Z")

    until_now = iso(clock.now())
    clock.advance(hours=2)
    assert audit(client, admin, f"&date_to={until_now}")
    assert audit(client, admin, f"&date_from={iso(clock.now())}") == []


def test_target_filter_treats_wildcards_as_text(client, admin, world):
    assert audit(client, admin, "&target=%25") == []  # "%" is not "anything"


def test_newest_first_and_paging(client, admin, world):
    lines = audit(client, admin)
    assert [line["id"] for line in lines] == sorted((line["id"] for line in lines), reverse=True)
    page = client.get("/api/audit?limit=2&offset=1", headers=admin).json()
    assert [line["id"] for line in page] == [line["id"] for line in lines[1:3]]


def test_audit_needs_the_right_and_has_no_write_route(client, admin, agent, world):
    assert client.get("/api/audit", headers=agent).status_code == 403
    assert client.get("/api/audit/actors", headers=agent).status_code == 403
    line_id = audit(client, admin)[0]["id"]
    assert client.delete(f"/api/audit/{line_id}", headers=admin).status_code in (404, 405)
    assert client.patch(f"/api/audit/{line_id}", headers=admin, json={}).status_code in (404, 405)


def test_export_uses_the_screen_filters_and_readable_columns(client, admin, world):
    zone = world["zone"]["id"]
    client.patch(f"/api/zones/{zone}/antipassback", headers=admin, json={"antipassback_mode": "SOUPLE"})
    sheet = load_workbook(BytesIO(client.get("/api/exports/audit.xlsx?action=zone", headers=admin).content)).active
    assert "Catégorie : Zones" in sheet["A3"].value
    header = [c.value for c in sheet[4]]
    assert header == ["Date et heure", "Auteur", "Action", "Objet", "Détail", "Adresse IP"]
    rows = list(sheet.iter_rows(min_row=5, values_only=True))
    assert rows[0][2] == "Contrôle des entrées changé" and rows[0][4].startswith("Contrôle des entrées : ")
    assert rows[0][5] == "testclient"
    export_line = audit(client, admin, "&action=export")[0]
    assert export_line["detail"]["filters"] == {"action": "zone"}
