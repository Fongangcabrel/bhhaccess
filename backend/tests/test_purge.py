"""Tâche 31: filtered purge of the journal with a preview, bulk removal of photos (FR-97, FR-98)."""
from pathlib import Path

from tests.test_api_flow import scan
from tests.test_photos import image_bytes, upload


def purge(client, headers, **body):
    return client.post("/api/logs/purge", headers=headers, json=body)


def logs(client, admin, **params):
    return client.get("/api/logs", headers=admin, params=params).json()


def second_person(client, admin):
    """An employee of « Production » with a badge but no access: their scans are refused (and logged)."""
    prod = client.post("/api/org/departments", headers=admin, json={"name": "Production"}).json()
    person = client.post("/api/employees", headers=admin, json={
        "matricule": "P-7", "last_name": "Abena", "first_name": "Marie", "department_id": prod["id"]}).json()
    badge = client.post("/api/badges", headers=admin, json={"employee_id": person["id"]}).json()
    token = client.get(f"/api/badges/{badge['id']}/qr-token", headers=admin).json()["token"]
    return prod, person, token


def test_preview_then_purge_by_department(client, admin, agent, world, clock):
    prod, person, token = second_person(client, admin)
    scan(client, agent, world["entry"], world["token"])
    clock.advance(minutes=5)
    scan(client, agent, world["entry"], token)
    assert len(logs(client, admin)) == 2

    preview = purge(client, admin, department_id=prod["id"], dry_run=True).json()
    assert preview == {"deleted": 1, "dry_run": True, "filters": ["Département : Production"]}
    assert len(logs(client, admin)) == 2  # the preview deleted nothing

    assert purge(client, admin, department_id=prod["id"]).json()["deleted"] == 1
    remaining = logs(client, admin)
    assert [line["employee_id"] for line in remaining] == [world["employee"]["id"]]
    entry = client.get("/api/audit?action=logs.purge", headers=admin).json()[0]
    assert entry["target"] == "Département : Production" and entry["detail"]["deleted"] == 1


def test_purge_combines_employee_zone_and_period(client, admin, agent, world, clock):
    scan(client, agent, world["entry"], world["token"])
    clock.advance(hours=1)
    start = clock.now()
    scan(client, agent, world["exit"], world["token"])
    clock.advance(hours=1)
    body = {"employee_id": world["employee"]["id"], "zone_id": world["zone"]["id"],
            "date_from": start.isoformat()}
    assert purge(client, admin, **body, dry_run=True).json()["deleted"] == 1
    assert purge(client, admin, **body).json()["deleted"] == 1
    assert len(logs(client, admin)) == 1  # the first entry, before the period, is kept
    assert purge(client, admin, before=clock.now().isoformat()).json()["deleted"] == 1  # old form


def test_purge_needs_a_filter_the_right_and_aware_dates(client, admin, agent, world):
    assert purge(client, admin).status_code == 400
    en = purge(client, {**admin, "Accept-Language": "en"}, dry_run=True)
    assert en.json()["detail"] == "Choose at least one filter (period, employee, department, entity or zone)"
    assert purge(client, agent, zone_id=world["zone"]["id"]).status_code == 403
    assert purge(client, admin, date_from="2026-01-01T00:00:00").status_code == 422  # no time zone


def test_photos_removed_in_bulk_after_a_count(client, admin, world, app):
    prod, person, _ = second_person(client, admin)
    for employee_id in (world["employee"]["id"], person["id"]):
        assert upload(client, admin, employee_id, image_bytes()).status_code == 200
    photos_dir = app.state.photos_dir
    assert len(list(Path(photos_dir).glob("*.jpg"))) == 2

    body = {"department_id": prod["id"]}
    preview = client.post("/api/photos/purge", headers=admin, json={**body, "dry_run": True}).json()
    assert preview == {"deleted": 1, "dry_run": True, "filters": ["Département : Production"]}
    assert client.post("/api/photos/purge", headers=admin, json=body).json()["deleted"] == 1
    assert client.get(f"/api/employees/{person['id']}", headers=admin).json()["has_photo"] is False
    assert client.get(f"/api/employees/{world['employee']['id']}", headers=admin).json()["has_photo"] is True
    assert len(list(Path(photos_dir).glob("*.jpg"))) == 1  # the file is gone too
    assert client.get("/api/audit?action=photos.purge", headers=admin).json()[0]["detail"]["deleted"] == 1


def test_photos_of_archived_people_only(client, admin, world, agent):
    _, person, _ = second_person(client, admin)
    for employee_id in (world["employee"]["id"], person["id"]):
        upload(client, admin, employee_id, image_bytes())
    client.post(f"/api/employees/{person['id']}/archive", headers=admin, json={"reason": "Départ"})
    body = {"archived_only": True}
    assert client.post("/api/photos/purge", headers=admin, json={**body, "dry_run": True}).json()["deleted"] == 1
    assert client.post("/api/photos/purge", headers=agent, json=body).status_code == 403
    assert client.post("/api/photos/purge", headers=admin, json={}).status_code == 400
    assert client.post("/api/photos/purge", headers=admin, json={"department_id": 9999}).status_code == 404
