"""Tâche 36: entities and departments, two separate lists managed from the console."""


def org(client, admin):
    return client.get("/api/org", headers=admin).json()


def new_entity(client, admin, name):
    return client.post("/api/org/entities", headers=admin, json={"name": name})


def new_department(client, admin, name):
    return client.post("/api/org/departments", headers=admin, json={"name": name})


def employee(client, admin, matricule, **org_ids):
    body = {"matricule": matricule, "last_name": "A", "first_name": "B", **org_ids}
    return client.post("/api/employees", headers=admin, json=body)


def test_two_independent_lists_with_employee_counts(client, admin):
    entity = new_entity(client, admin, "  BHH   Industrie ")
    assert entity.status_code == 201 and entity.json()["name"] == "BHH Industrie"
    other = new_entity(client, admin, "BHH Logistique").json()
    rh = new_department(client, admin, "Ressources humaines").json()
    assert "entity_id" not in rh  # a department belongs to no entity
    # The same department serves several entities.
    employee(client, admin, "E1", entity_id=entity.json()["id"], department_id=rh["id"])
    employee(client, admin, "E2", entity_id=other["id"], department_id=rh["id"])
    employee(client, admin, "E3", department_id=rh["id"])  # a department without entity is fine
    data = org(client, admin)
    assert [(e["name"], e["employees"]) for e in data["entities"]] == [("BHH Industrie", 1), ("BHH Logistique", 1)]
    assert data["departments"] == [{"id": rh["id"], "name": "Ressources humaines", "employees": 3}]


def test_rename_is_seen_everywhere(client, admin):
    eid = new_entity(client, admin, "BHH Industrie").json()["id"]
    did = new_department(client, admin, "Production").json()["id"]
    employee(client, admin, "E1", entity_id=eid, department_id=did)
    assert client.patch(f"/api/org/entities/{eid}", headers=admin, json={"name": "BHH Industries"}).status_code == 200
    renamed = client.patch(f"/api/org/departments/{did}", headers=admin, json={"name": "Usinage"})
    assert renamed.json()["name"] == "Usinage"
    person = client.get("/api/employees?q=E1", headers=admin).json()[0]
    assert person["entity_name"] == "BHH Industries" and person["department_name"] == "Usinage"
    assert client.get("/api/org/departments", headers=admin).json() == [{"id": did, "name": "Usinage"}]


def test_duplicates_are_refused_case_insensitive(client, admin):
    new_entity(client, admin, "BHH Logistique")
    assert new_entity(client, admin, "bhh logistique").status_code == 409
    new_department(client, admin, "Transport")
    assert new_department(client, admin, "TRANSPORT").status_code == 409
    assert new_entity(client, admin, "   ").status_code == 400


def test_delete_only_what_nobody_uses(client, admin):
    eid = new_entity(client, admin, "BHH Agro").json()["id"]
    did = new_department(client, admin, "Qualité").json()["id"]
    person = employee(client, admin, "E2", entity_id=eid, department_id=did).json()
    assert client.delete(f"/api/org/departments/{did}", headers=admin).status_code == 409
    assert client.delete(f"/api/org/entities/{eid}", headers=admin).status_code == 409
    client.patch(f"/api/employees/{person['id']}", headers=admin, json={"department_id": None, "entity_id": None})
    assert client.delete(f"/api/org/departments/{did}", headers=admin).status_code == 204
    assert client.delete(f"/api/org/entities/{eid}", headers=admin).status_code == 204
    actions = [a["action"] for a in client.get("/api/audit?action=department", headers=admin).json()]
    assert actions == ["department.delete", "department.create"]


def test_employee_needs_existing_entity_and_department(client, admin):
    assert employee(client, admin, "E3", entity_id=9999).status_code == 404
    assert employee(client, admin, "E3", department_id=9999).status_code == 404
    did = new_department(client, admin, "RH").json()["id"]
    created = employee(client, admin, "E3", department_id=did).json()
    moved = client.patch(f"/api/employees/{created['id']}", headers=admin, json={"department_id": 9999})
    assert moved.status_code == 404


def test_rights(client, admin, agent, make_user):
    assert client.get("/api/org", headers=agent).status_code == 403
    rh = make_user("rh1", "rh")
    assert new_entity(client, rh, "BHH Immo").status_code == 201
    assert new_department(client, agent, "X").status_code == 403
