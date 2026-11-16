"""Exports (tâches 18 à 21): Excel, printable PDF, badge PDF, rights and audit trail."""
from io import BytesIO

from openpyxl import load_workbook


def scan(client, headers, checkpoint, token):
    client.post("/api/scan", headers=headers, json={"checkpoint_id": checkpoint["id"], "token": token})


def audit_actions(client, admin):
    return [a for a in client.get("/api/audit?limit=500", headers=admin).json() if a["action"].startswith("export")]


def test_journal_excel_has_screen_columns_local_time_and_filters(client, agent, admin, world):
    scan(client, agent, world["entry"], world["token"])
    scan(client, agent, world["exit"], world["token"])
    response = client.get(f"/api/exports/journal.xlsx?zone_id={world['zone']['id']}&direction=SORTIE", headers=admin)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert 'filename="journal-passages-' in response.headers["content-disposition"]
    sheet = load_workbook(BytesIO(response.content)).active
    assert sheet["A1"].value == "Journal des passages"
    assert "Zone : Usine" in sheet["A3"].value and "Sens : Sortie" in sheet["A3"].value
    header = [c.value for c in sheet[4]]
    assert header[:3] == ["Date et heure", "Matricule", "Nom"] and "Résultat" in header
    rows = list(sheet.iter_rows(min_row=5, values_only=True))
    assert len(rows) == 1 and rows[0][1] == "EMP-0042" and rows[0][10] == "Sortie enregistrée"
    assert rows[0][0].hour == 9  # 08:00 UTC shown in Douala time (UTC+1)
    assert sheet["A5"].number_format == "dd/mm/yyyy hh:mm:ss"
    assert sheet.column_dimensions["A"].width >= 24
    assert sheet.freeze_panes == "A5" and sheet.auto_filter.ref == "A4:N5"


def test_journal_export_can_include_only_selected_log_ids(client, agent, admin, world):
    selected = client.post(
        "/api/scan", headers=agent, json={"checkpoint_id": world["entry"]["id"], "token": world["token"]}
    ).json()
    client.post("/api/scan", headers=agent, json={"checkpoint_id": world["exit"]["id"], "token": world["token"]})

    response = client.get(f"/api/exports/journal.xlsx?log_ids={selected['log_id']}", headers=admin)
    sheet = load_workbook(BytesIO(response.content)).active
    rows = list(sheet.iter_rows(min_row=5, values_only=True))

    assert response.status_code == 200
    assert len(rows) == 1 and rows[0][8] == "Entrée"
    assert sheet["A3"].value.endswith("1 passage(s) sélectionné(s)")


def test_formula_injection_is_neutralised(client, agent, admin, world):
    client.patch(f"/api/employees/{world['employee']['id']}", headers=admin,
                 json={"first_name": '=HYPERLINK("http://evil","x")'})  # "Nom" = first + last name
    scan(client, agent, world["entry"], world["token"])
    sheet = load_workbook(BytesIO(client.get("/api/exports/journal.xlsx", headers=admin).content)).active
    name = sheet.cell(row=5, column=3)
    assert name.data_type == "s" and name.value.startswith("'=")  # text, never a formula
    csv = client.get("/api/logs/export.csv", headers=admin).text
    assert '\'=HYPERLINK' in csv


def test_journal_pdf_is_a_landscape_document_with_page_numbers(client, agent, admin, world):
    for _ in range(3):
        scan(client, agent, world["entry"], world["token"])
    response = client.get("/api/exports/journal.pdf", headers=admin)
    assert response.status_code == 200 and response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def test_export_needs_view_and_export_rights(client, agent, admin, make_user, world):
    assert client.get("/api/exports/journal.xlsx", headers=agent).status_code == 403
    rh = make_user("rh1", "rh")
    rh_id = next(u["id"] for u in client.get("/api/users", headers=admin).json() if u["username"] == "rh1")
    assert client.get("/api/exports/journal.xlsx", headers=rh).status_code == 200
    client.put(f"/api/users/{rh_id}/overrides", headers=admin, json={"permission": "logs.view", "effect": "deny"})
    assert client.get("/api/exports/journal.xlsx", headers=rh).status_code == 403  # export alone is not enough
    assert client.get("/api/exports/journal.docx", headers=admin).status_code == 422


def test_every_export_is_audited(client, admin, world):
    client.get("/api/exports/journal.pdf?verdict=AUTORISE", headers=admin)
    client.get("/api/exports/employees.xlsx", headers=admin)
    client.get("/api/logs/export.csv", headers=admin)
    entries = audit_actions(client, admin)[::-1]  # the audit lists newest first
    assert [(e["action"], e["target"]) for e in entries] == [
        ("export.pdf", "journal"), ("export.xlsx", "employees"), ("export.csv", "journal")]
    assert entries[0]["detail"]["filters"] == {"verdict": "AUTORISE"} and "rows" in entries[0]["detail"]


def test_audit_and_employee_exports(client, admin, world):
    audit = load_workbook(BytesIO(client.get("/api/exports/audit.xlsx?action=badge", headers=admin).content)).active
    actions = [row[2] for row in audit.iter_rows(min_row=5, values_only=True)]
    assert actions and all(a.startswith("Badge") for a in actions)  # readable labels
    people = load_workbook(BytesIO(client.get("/api/exports/employees.xlsx", headers=admin).content)).active
    assert [row[0] for row in people.iter_rows(min_row=5, values_only=True)] == ["EMP-0042"]
    assert client.get("/api/exports/audit.pdf", headers=admin).content.startswith(b"%PDF")


def test_badge_print_pdf(client, agent, admin, world):
    url = f"/api/badges/{world['badge']['id']}/print.pdf"
    response = client.get(url, headers=admin)
    assert response.status_code == 200 and response.content.startswith(b"%PDF")
    assert 'badge-EMP-0042-v1.pdf' in response.headers["content-disposition"]
    assert client.get(url, headers=agent).status_code == 403
    client.post(f"/api/badges/{world['badge']['id']}/revoke", headers=admin, json={"reason": "PERTE"})
    assert client.get(url, headers=admin).status_code == 400
    assert any(a["action"] == "badge.print" for a in client.get("/api/audit?limit=500", headers=admin).json())
