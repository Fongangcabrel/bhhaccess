"""Endpoints that feed the back-office screens."""


def scan(client, agent, checkpoint, token):
    client.app.state.clock.advance(seconds=4)  # distinct passages: a repeat within 3 s counts once
    return client.post("/api/scan", headers=agent, json={"checkpoint_id": checkpoint["id"], "token": token}).json()


def test_dashboard_counts_and_presence(client, agent, admin, world):
    scan(client, agent, world["entry"], world["token"])
    scan(client, agent, world["entry"], world["token"])  # refused: already inside
    stats = client.get("/api/stats/today", headers=admin).json()
    assert stats["total"] == 2 and stats["entries_authorized"] == 1 and stats["refused"] == 1
    assert stats["inside"] == 1
    inside = client.get("/api/presence", headers=admin).json()
    assert inside[0]["matricule"] == "EMP-0042" and inside[0]["zone_name"] == "Usine"
    scan(client, agent, world["exit"], world["token"])
    assert client.get("/api/presence", headers=admin).json() == []
    assert client.get("/api/stats/today", headers=admin).json()["exits"] == 1


def test_stats_are_guarded(client, agent):
    assert client.get("/api/stats/today", headers=agent).status_code == 403
    assert client.get("/api/presence", headers=agent).status_code == 403


def test_journal_rows_carry_names(client, agent, admin, world):
    scan(client, agent, world["entry"], world["token"])
    row = client.get("/api/logs", headers=admin).json()[0]
    assert row["employee_name"] == "Paul Ngono" and row["zone_name"] == "Usine"
    assert row["checkpoint_name"] == "Entrée usine"


def test_csv_export_is_excel_friendly_and_needs_export_right(client, agent, admin, make_user, world):
    scan(client, agent, world["entry"], world["token"])
    assert client.get("/api/logs/export.csv", headers=agent).status_code == 403
    response = client.get("/api/logs/export.csv", headers=admin)
    assert response.status_code == 200 and "attachment" in response.headers["content-disposition"]
    text = response.content.decode("utf-8")
    assert text.startswith("﻿Date;Heure;Matricule")
    assert "EMP-0042;Paul Ngono" in text and "AUTORISE" in text


def test_employee_badges_and_authorizations(client, admin, world):
    employee_id = world["employee"]["id"]
    client.post("/api/badges", headers=admin, json={"employee_id": employee_id})  # re-issue
    badges = client.get(f"/api/employees/{employee_id}/badges", headers=admin).json()
    assert [b["version"] for b in badges] == [2, 1] and badges[1]["status"] == "REVOQUE"
    auths = client.get(f"/api/employees/{employee_id}/authorizations", headers=admin).json()
    assert [a["zone_id"] for a in auths] == [world["zone"]["id"]]


def test_org_lists_and_employee_names(client, admin):
    import io

    from openpyxl import Workbook

    wb = Workbook()
    wb.active.append(["Matricule", "Nom", "Prénom", "Entité", "Département"])
    wb.active.append(["E9", "Test", "Anne", "BHH", "IT"])
    buffer = io.BytesIO()
    wb.save(buffer)
    client.post("/api/employees/import", headers=admin, params={"create_missing_org": True},
                files={"file": ("e.xlsx", buffer.getvalue())})
    assert [e["name"] for e in client.get("/api/org/entities", headers=admin).json()] == ["BHH"]
    assert [d["name"] for d in client.get("/api/org/departments", headers=admin).json()] == ["IT"]
    employee = client.get("/api/employees", headers=admin, params={"q": "Test"}).json()[0]
    assert employee["entity_name"] == "BHH" and employee["department_name"] == "IT"
