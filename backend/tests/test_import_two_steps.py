"""Tâche 29: Excel import in two steps (check, then create), template, refused rows file, size limit."""
from io import BytesIO

from openpyxl import load_workbook

from tests.test_users_import_qr import workbook

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def send(client, headers, url, content, create=False, name="rh-novembre.xlsx"):
    return client.post(url, headers=headers, params={"create_missing_org": create},
                       files={"file": (name, content, XLSX)})


ROWS = [
    ["E1", "Ngono", "Paul", "BHH", "IT", "Dev", "Douala"],
    ["E1", "Doublon", "Jean", "BHH", "IT", "Dev", None],
    [None, "SansMatricule", "Zoe", None, None, None, None],
    ["E4", "X" * 130, "Long", None, None, None, None],
]


def test_check_writes_nothing_then_import_creates(client, admin):
    content = workbook(ROWS)
    check = send(client, admin, "/api/employees/import/check", content, create=True).json()
    assert check["file_name"] == "rh-novembre.xlsx"
    assert (check["total"], check["valid"]) == (4, 1)
    assert check["new_entities"] == ["BHH"] and check["new_departments"] == ["IT"]
    assert check["preview"][0] == {"row": 2, "matricule": "E1", "last_name": "Ngono", "first_name": "Paul",
                                   "entity": "BHH", "department": "IT", "job_title": "Dev"}
    reasons = {r["row"]: r["errors"] for r in check["rejected"]}
    assert reasons == {3: ["matricule en double dans le fichier"], 4: ["matricule manquant"],
                       5: ["nom trop long : 120 caractères maximum"]}
    # Nothing was written by the check.
    assert client.get("/api/employees", headers=admin, params={"q": "Ngono"}).json() == []
    assert client.get("/api/org", headers=admin).json()["entities"] == []

    report = send(client, admin, "/api/employees/import", content, create=True).json()
    assert report["created"] == 1 and len(report["rejected"]) == 3
    line = next(a for a in client.get("/api/audit?action=employee.import", headers=admin).json())
    assert line["target"] == "rh-novembre.xlsx"


def test_refused_rows_file_can_be_fixed_and_imported(client, admin):
    content = workbook(ROWS)
    response = send(client, admin, "/api/employees/import/rejected.xlsx", content, create=True)
    assert response.status_code == 200 and response.headers["content-type"] == XLSX
    sheet = load_workbook(BytesIO(response.content)).active
    rows = list(sheet.iter_rows(values_only=True))
    assert rows[0] == ("Matricule", "Nom", "Prénom", "Entité", "Département", "Fonction", "Site", "Erreurs")
    assert [r[0] for r in rows[1:]] == ["E1", None, "E4"] and rows[1][-1] == "matricule en double dans le fichier"
    # Fix the rows in Excel (new numbers, shorter name), drop the « Erreurs » column, import again.
    fixed = workbook([["E2", "Doublon", "Jean", "BHH", "IT", "Dev", None], ["E3", "SansMatricule", "Zoe"] + [None] * 4])
    assert send(client, admin, "/api/employees/import/check", fixed, create=True).json()["valid"] == 2


def test_template_is_recognised(client, admin):
    response = client.get("/api/employees/import/template.xlsx", headers=admin)
    assert response.status_code == 200
    book = load_workbook(BytesIO(response.content))
    assert book.sheetnames == ["Employés", "Mode d'emploi"]
    check = send(client, admin, "/api/employees/import/check", response.content, create=True).json()
    assert check["valid"] == 1 and check["preview"][0]["matricule"] == "EMP-0001"
    english = client.get("/api/employees/import/template.xlsx", headers={**admin, "Accept-Language": "en"})
    guide = load_workbook(BytesIO(english.content))["Mode d'emploi"]["A1"].value
    assert guide.startswith("Employee import")


def test_limits_and_translated_reasons(client, admin, app):
    app.state.import_max_bytes = 2000
    too_big = send(client, admin, "/api/employees/import/check", workbook(ROWS))
    assert too_big.status_code == 400 and too_big.json()["detail"] == "Fichier trop lourd : 0 Mo maximum"
    app.state.import_max_bytes = 5 * 1024 * 1024
    en = send(client, {**admin, "Accept-Language": "en"}, "/api/employees/import/check", workbook(ROWS)).json()
    reasons = {r["row"]: r["errors"] for r in en["rejected"]}
    assert reasons[2] == ["unknown entity: BHH", "unknown department: IT"]
    assert reasons[5] == ["last name too long: 120 characters maximum"]


def test_check_needs_the_import_right(client, agent):
    assert send(client, agent, "/api/employees/import/check", workbook([])).status_code == 403
    assert client.get("/api/employees/import/template.xlsx", headers=agent).status_code == 403
