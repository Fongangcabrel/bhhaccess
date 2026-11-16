"""Tâche 30: bulk changes on employees (FR-28) and zones given to a whole department (FR-42)."""


def bulk(client, headers, **body):
    return client.post("/api/employees/bulk", headers=headers, json=body)


def staff(client, admin):
    """Three employees in « Production », one in « Logistique »."""
    prod = client.post("/api/org/departments", headers=admin, json={"name": "Production"}).json()
    logi = client.post("/api/org/departments", headers=admin, json={"name": "Logistique"}).json()
    people = []
    rows = [("P1", "Abena", prod), ("P2", "Biya", prod), ("P3", "Chi", prod), ("L1", "Dang", logi)]
    for matricule, last, dept in rows:
        people.append(client.post("/api/employees", headers=admin, json={
            "matricule": matricule, "last_name": last, "first_name": "X", "department_id": dept["id"]}).json())
    return prod, logi, people


def authorized(client, admin, employee_id):
    return {a["zone_id"] for a in client.get(f"/api/employees/{employee_id}/authorizations", headers=admin).json()}


def test_suspend_a_selection_reports_unchanged_and_failures(client, admin):
    _, _, (p1, p2, p3, _) = staff(client, admin)
    client.patch(f"/api/employees/{p2['id']}/status", headers=admin, json={"status": "SUSPENDU"})
    client.post(f"/api/employees/{p3['id']}/archive", headers=admin, json={"reason": "Départ"})
    out = bulk(client, admin, action="suspend", employee_ids=[p1["id"], p2["id"], p3["id"]]).json()
    assert (out["total"], out["done"], out["unchanged"]) == (3, 1, 1)
    assert out["failed"] == [{"employee_id": p3["id"], "matricule": "P3",
                              "reason": "Employé archivé : utilisez « Restaurer »"}]
    assert client.get(f"/api/employees/{p1['id']}", headers=admin).json()["status"] == "SUSPENDU"
    actions = [a["action"] for a in client.get("/api/audit?limit=20", headers=admin).json()]
    assert actions[0] == "employee.bulk" and "employee.status" in actions
    reactivated = bulk(client, admin, action="reactivate", employee_ids=[p1["id"], p2["id"]]).json()
    assert reactivated["done"] == 2


def test_change_department_only_and_clear_the_entity(client, admin):
    prod, logi, (p1, p2, _, _) = staff(client, admin)
    entity = client.post("/api/org/entities", headers=admin, json={"name": "BHH Industrie"}).json()
    out = bulk(client, admin, action="org", employee_ids=[p1["id"], p2["id"]], entity_id=entity["id"]).json()
    assert out["done"] == 2
    moved = bulk(client, admin, action="org", employee_ids=[p1["id"]], department_id=logi["id"]).json()
    assert moved["done"] == 1
    first = client.get(f"/api/employees/{p1['id']}", headers=admin).json()
    assert first["department_id"] == logi["id"] and first["entity_id"] == entity["id"]  # entity kept
    cleared = bulk(client, admin, action="org", employee_ids=[p1["id"]], entity_id=None).json()
    assert cleared["done"] == 1 and client.get(f"/api/employees/{p1['id']}", headers=admin).json()["entity_id"] is None
    assert bulk(client, admin, action="org", employee_ids=[p1["id"]]).status_code == 400


def test_zones_given_to_a_whole_department(client, admin, world):
    prod, _, (p1, p2, p3, l1) = staff(client, admin)
    zone = world["zone"]["id"]
    client.put("/api/authorizations", headers=admin, json={"employee_id": p2["id"], "zone_id": zone})
    client.post(f"/api/employees/{p3['id']}/archive", headers=admin, json={"reason": "Départ"})
    preview = bulk(client, admin, action="add_zones", in_department_id=prod["id"], zone_ids=[zone], dry_run=True).json()
    assert (preview["total"], preview["done"], preview["target"]) == (2, 0, "département Production")
    assert zone not in authorized(client, admin, p1["id"])  # the preview changed nothing
    out = bulk(client, admin, action="add_zones", in_department_id=prod["id"], zone_ids=[zone]).json()
    assert (out["done"], out["unchanged"]) == (1, 1)  # P2 already had it; archived P3 not concerned
    assert zone in authorized(client, admin, p1["id"]) and zone not in authorized(client, admin, l1["id"])
    removed = bulk(client, admin, action="remove_zones", in_department_id=prod["id"], zone_ids=[zone]).json()
    assert removed["done"] == 2 and zone not in authorized(client, admin, p2["id"])
    summary = client.get("/api/audit?action=employee.bulk", headers=admin).json()[0]
    assert summary["target"] == "département Production"


def test_bulk_archive_needs_a_reason_and_the_right(client, admin, make_user):
    _, _, (p1, p2, _, _) = staff(client, admin)
    assert bulk(client, admin, action="archive", employee_ids=[p1["id"]]).status_code == 400
    hr = make_user("rh1", "rh")
    assert bulk(client, hr, action="archive", employee_ids=[p1["id"]], reason="Fin de contrat").status_code == 403
    assert bulk(client, hr, action="suspend", employee_ids=[p1["id"]]).json()["done"] == 1
    out = bulk(client, admin, action="archive", employee_ids=[p1["id"], p2["id"]], reason="Fin de contrat").json()
    assert out["done"] == 2
    assert client.get(f"/api/employees/{p2['id']}", headers=admin).json()["status"] == "ARCHIVE"


def test_bad_requests(client, admin, agent):
    assert bulk(client, agent, action="suspend", employee_ids=[1]).status_code == 403
    assert bulk(client, admin, action="suspend").status_code == 400
    assert bulk(client, admin, action="suspend", employee_ids=[99999]).status_code == 404
    _, _, (p1, *_rest) = staff(client, admin)
    assert bulk(client, admin, action="add_zones", employee_ids=[p1["id"]], zone_ids=[]).status_code == 400
    en = bulk(client, {**admin, "Accept-Language": "en"}, action="add_zones", employee_ids=[p1["id"]])
    assert en.json()["detail"] == "Choose at least one zone"
