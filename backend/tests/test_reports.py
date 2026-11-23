"""Tâche 32: reports over a period (FR-73 movements, FR-77 presence by zone and refusal trends)."""
from io import BytesIO

from openpyxl import load_workbook

from tests.conftest import _login


def next_day(client, clock, days=1):
    """Move the clock on; sessions last 8 h, so both operators log in again."""
    clock.advance(days=days)
    return _login(client, "admin", "pw-admin"), _login(client, "agent1", "pw")


def scan(client, headers, checkpoint, token):
    return client.post("/api/scan", headers=headers, json={"checkpoint_id": checkpoint["id"], "token": token}).json()


def setup_people(client, admin, world):
    """Paul (Production, authorised) and Awa (Logistique, no access to the zone)."""
    prod = client.post("/api/org/departments", headers=admin, json={"name": "Production"}).json()
    logi = client.post("/api/org/departments", headers=admin, json={"name": "Logistique"}).json()
    client.patch(f"/api/employees/{world['employee']['id']}", headers=admin, json={"department_id": prod["id"]})
    awa = client.post("/api/employees", headers=admin, json={
        "matricule": "EMP-0077", "last_name": "Bella", "first_name": "Awa", "department_id": logi["id"]}).json()
    badge = client.post("/api/badges", headers=admin, json={"employee_id": awa["id"]}).json()
    token = client.get(f"/api/badges/{badge['id']}/qr-token", headers=admin).json()["token"]
    return {"prod": prod, "logi": logi, "awa": awa, "awa_token": token}


def morning(client, agent, world, people):
    scan(client, agent, world["entry"], world["token"])  # AUTORISE
    scan(client, agent, world["entry"], world["token"])  # REFUSE_ANTIPASSBACK (strict zone)
    scan(client, agent, world["exit"], world["token"])  # SORTIE_ENREGISTREE
    scan(client, agent, world["entry"], people["awa_token"])  # REFUSE_ZONE
    scan(client, agent, world["entry"], people["awa_token"])  # REFUSE_ZONE


def test_movements_per_employee_and_zone(client, agent, admin, world, clock):
    people = setup_people(client, admin, world)
    morning(client, agent, world, people)
    admin, agent = next_day(client, clock)
    scan(client, agent, world["entry"], world["token"])
    payload = {"employee_id": world["employee"]["id"], "zone_id": world["zone"]["id"],
               "reason": "Sorti sans scanner", "mode": "sortie"}
    assert client.post("/api/presence/unblock", headers=admin, json=payload).status_code == 204

    report = client.get("/api/reports/movements", headers=admin).json()
    assert report["employees"] == 2 and report["entries"] == 2 and report["exits"] == 1
    awa, paul = report["rows"]  # sorted by name: Awa Bella, Paul Ngono
    assert (awa["matricule"], awa["entries"], awa["refused"]) == ("EMP-0077", 0, 2)
    assert awa["department_name"] == "Logistique"
    assert (paul["entries"], paul["exits"], paul["refused"], paul["unblocks"]) == (2, 1, 1, 1)  # unblock apart
    assert paul["zone_name"] == "Usine" and paul["first_at"] < paul["last_at"]

    only_prod = client.get(f"/api/reports/movements?department_id={people['prod']['id']}", headers=admin).json()
    assert [r["matricule"] for r in only_prod["rows"]] == ["EMP-0042"]
    first_day = client.get("/api/reports/movements", headers=admin,
                           params={"date_from": "2026-11-11T00:00:00", "date_to": "2026-11-11T23:59:59"}).json()
    assert first_day["entries"] == 1  # a date without time zone is read as Douala time, not a 500


def test_presence_by_zone_counts_inside_now_and_people(client, agent, admin, world):
    people = setup_people(client, admin, world)
    morning(client, agent, world, people)
    scan(client, agent, world["entry"], world["token"])  # Paul is inside again
    free = client.post("/api/zones", headers=admin, json={"name": "Cantine", "antipassback_mode": "DESACTIVE"}).json()

    rows = {r["zone_name"]: r for r in client.get("/api/reports/presence", headers=admin).json()["rows"]}
    usine = rows["Usine"]
    assert (usine["inside_now"], usine["people"], usine["entries"], usine["exits"], usine["refused"]) == (1, 1, 2, 1, 3)
    assert rows["Cantine"]["inside_now"] is None and rows["Cantine"]["entries"] == 0  # "Libre": not tracked
    logi = client.get(f"/api/reports/presence?department_id={people['logi']['id']}&zone_id={world['zone']['id']}",
                      headers=admin).json()
    assert len(logi["rows"]) == 1 and logi["rows"][0]["inside_now"] == 0 and logi["rows"][0]["refused"] == 2
    assert free["id"] not in [r["zone_id"] for r in logi["rows"]]


def test_refusal_trend_by_day_reason_zone_and_person(client, agent, admin, world, clock):
    people = setup_people(client, admin, world)
    morning(client, agent, world, people)
    admin, agent = next_day(client, clock, days=2)
    scan(client, agent, world["entry"], people["awa_token"])

    trend = client.get("/api/reports/refusals", headers=admin,
                       params={"date_from": "2026-11-11T00:00:00+01:00", "date_to": "2026-11-13T23:59:59+01:00"}).json()
    assert [d["total"] for d in trend["days"]] == [3, 0, 1]  # the empty day is kept
    assert trend["days"][0]["day"] == "2026-11-11" and trend["days"][0]["by_verdict"]["REFUSE_ZONE"] == 2
    assert trend["total"] == 4 and trend["previous_total"] == 0
    assert trend["by_verdict"] == {"REFUSE_ZONE": 3, "REFUSE_ANTIPASSBACK": 1}
    assert trend["by_zone"][0]["zone_name"] == "Usine" and trend["by_zone"][0]["count"] == 4
    assert [(p["matricule"], p["count"]) for p in trend["by_employee"]] == [("EMP-0077", 3), ("EMP-0042", 1)]

    default = client.get("/api/reports/refusals", headers=admin).json()  # last 30 days
    assert len(default["days"]) == 30 and default["total"] == 4
    later = client.get("/api/reports/refusals", headers=admin,
                       params={"date_from": "2026-11-14T00:00:00+01:00", "date_to": "2026-11-16T23:59:59+01:00"}).json()
    assert later["total"] == 0 and later["previous_total"] == 4  # the 3 days just before


def test_bad_periods_are_refused_with_a_message(client, admin):
    too_long = client.get("/api/reports/refusals", headers=admin,
                          params={"date_from": "2025-01-01T00:00:00+01:00", "date_to": "2026-11-11T00:00:00+01:00"})
    assert too_long.status_code == 400 and "366 jours" in too_long.json()["detail"]
    reversed_ = client.get("/api/reports/movements", headers=admin,
                           params={"date_from": "2026-11-12T00:00:00+01:00", "date_to": "2026-11-11T00:00:00+01:00"})
    assert reversed_.status_code == 400


def test_reports_need_reports_view_and_exports_are_audited(client, agent, admin, make_user, world):
    people = setup_people(client, admin, world)
    morning(client, agent, world, people)
    assert client.get("/api/reports/movements", headers=agent).status_code == 403
    rh = make_user("rh1", "rh")
    assert client.get("/api/reports/presence", headers=rh).status_code == 200

    response = client.get(f"/api/exports/movements.xlsx?department_id={people['logi']['id']}", headers=rh)
    assert response.status_code == 200 and 'filename="mouvements-' in response.headers["content-disposition"]
    sheet = load_workbook(BytesIO(response.content)).active
    assert sheet["A1"].value == "Mouvements par employé et par zone"
    assert "Département : Logistique" in sheet["A3"].value
    header = [c.value for c in sheet[4]]
    rows = list(sheet.iter_rows(min_row=5, values_only=True))
    assert header[:2] == ["Matricule", "Nom"] and len(rows) == 1 and rows[0][header.index("Refus")] == 2

    for kind in ("presence", "refusals"):
        for fmt in ("xlsx", "pdf"):
            assert client.get(f"/api/exports/{kind}.{fmt}", headers=rh).status_code == 200
    trend = load_workbook(BytesIO(client.get("/api/exports/refusals.xlsx", headers=rh).content)).active
    assert [c.value for c in trend[4]][:3] == ["Jour", "Refus", "Zone non autorisée"]
    assert "période précédente" in trend["A3"].value

    exported = [a for a in client.get("/api/audit?limit=100", headers=admin).json() if a["action"].startswith("export")]
    assert {a["target"] for a in exported} == {"movements", "presence", "refusals"}
    assert client.get("/api/exports/movements.xlsx", headers=agent).status_code == 403
