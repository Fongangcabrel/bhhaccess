"""Employee lifecycle: edit, suspend, archive (QR non reconnu) and restore (tâches 1 à 4)."""


def scan(client, agent, checkpoint, token):
    response = client.post("/api/scan", headers=agent, json={"checkpoint_id": checkpoint["id"], "token": token})
    assert response.status_code == 200, response.text
    return response.json()


def archive(client, headers, employee_id, reason="Départ de l'entreprise"):
    return client.post(f"/api/employees/{employee_id}/archive", headers=headers, json={"reason": reason})


def logs(client, admin):
    return client.get("/api/logs", headers=admin).json()


# --- tâche 1 : un employé archivé = « QR non reconnu », sans identité -------------
def test_archived_employee_qr_reads_as_unrecognised_without_identity(client, agent, admin, world):
    assert archive(client, admin, world["employee"]["id"]).status_code == 200
    for gate in ("entry", "exit"):  # an exit is not recorded either: the QR is no longer known
        result = scan(client, agent, world[gate], world["token"])
        assert result["verdict"] == "REFUSE_INVALIDE"
        assert result["employee"] is None and result["flags"] == []
    journal = logs(client, admin)
    assert journal[0]["verdict"] == "REFUSE_INVALIDE"
    assert journal[0]["reason"] == "employe_archive"
    assert journal[0]["employee_matricule"] == "EMP-0042"  # back-office still sees who it was


def test_archived_employee_manual_entry_reads_as_unrecognised(client, agent, admin, world):
    archive(client, admin, world["employee"]["id"])
    response = client.post("/api/scan/manual", headers=agent,
                           json={"checkpoint_id": world["entry"]["id"], "matricule": "EMP-0042"})
    assert response.status_code == 200
    assert response.json()["verdict"] == "REFUSE_INVALIDE" and response.json()["employee"] is None
    assert logs(client, admin)[0]["reason"] == "employe_archive (saisie manuelle)"


def test_invalid_qr_reasons_are_logged(client, agent, admin, world):
    scan(client, agent, world["entry"], "not.a.token")
    assert logs(client, admin)[0]["reason"] == "signature_invalide"


# --- tâche 2 : archiver coupe tout ------------------------------------------------
def test_archive_revokes_badges_clears_presence_and_keeps_zones(client, agent, admin, world):
    employee_id = world["employee"]["id"]
    scan(client, agent, world["entry"], world["token"])  # inside the strict zone
    assert len(client.get("/api/presence", headers=admin).json()) == 1

    archived = archive(client, admin, employee_id).json()
    assert archived["status"] == "ARCHIVE"
    assert archived["archive_reason"] == "Départ de l'entreprise" and archived["archived_at"]
    badges = client.get(f"/api/employees/{employee_id}/badges", headers=admin).json()
    assert all(b["status"] == "REVOQUE" for b in badges)
    assert client.get("/api/presence", headers=admin).json() == []
    # Zones are kept so that a restore brings them back (App Flow 3.5).
    assert client.get(f"/api/employees/{employee_id}/authorizations", headers=admin).json()

    entry = next(a for a in client.get("/api/audit", headers=admin).json() if a["action"] == "employee.archive")
    assert entry["detail"]["reason"] == "Départ de l'entreprise" and entry["detail"]["badges_revoked"] == [1]


def test_archive_needs_a_reason_and_the_right(client, admin, make_user, world):
    employee_id = world["employee"]["id"]
    rh = make_user("rh1", "rh")  # RH may edit but not archive (SRS 2.2)
    assert archive(client, rh, employee_id).status_code == 403
    assert archive(client, admin, employee_id, reason=" ").status_code == 422
    assert archive(client, admin, employee_id).status_code == 200
    assert archive(client, admin, employee_id).status_code == 409


def test_status_route_cannot_archive_or_touch_an_archived_employee(client, admin, world):
    employee_id = world["employee"]["id"]
    url = f"/api/employees/{employee_id}/status"
    assert client.patch(url, headers=admin, json={"status": "ARCHIVE"}).status_code == 400
    archive(client, admin, employee_id)
    assert client.patch(url, headers=admin, json={"status": "ACTIF"}).status_code == 400


def test_no_badge_for_an_archived_employee(client, admin, world):
    archive(client, admin, world["employee"]["id"])
    response = client.post("/api/badges", headers=admin, json={"employee_id": world["employee"]["id"]})
    assert response.status_code == 400


# --- tâche 3 : restaurer -----------------------------------------------------------
def test_restore_brings_back_the_file_but_old_qr_stays_dead(client, agent, admin, world):
    employee_id = world["employee"]["id"]
    archive(client, admin, employee_id)
    restored = client.post(f"/api/employees/{employee_id}/restore", headers=admin)
    assert restored.status_code == 200
    assert restored.json()["status"] == "ACTIF" and restored.json()["archived_at"] is None

    # Old QR: badge revoked, never reactivated.
    assert scan(client, agent, world["entry"], world["token"])["verdict"] == "REFUSE_REVOQUE"
    # No badge issued automatically; a new one works with the zones that came back.
    badges = client.get(f"/api/employees/{employee_id}/badges", headers=admin).json()
    assert all(b["status"] == "REVOQUE" for b in badges)
    new_badge = client.post("/api/badges", headers=admin, json={"employee_id": employee_id}).json()
    token = client.get(f"/api/badges/{new_badge['id']}/qr-token", headers=admin).json()["token"]
    assert new_badge["version"] == 2
    assert scan(client, agent, world["entry"], token)["verdict"] == "AUTORISE"
    assert client.post(f"/api/employees/{employee_id}/restore", headers=admin).status_code == 409


# --- tâche 4 : modifier et filtrer ------------------------------------------------
def test_edit_employee_is_audited_with_before_and_after(client, admin, world):
    employee_id = world["employee"]["id"]
    response = client.patch(f"/api/employees/{employee_id}", headers=admin,
                            json={"first_name": "Paul-Henri", "job_title": "Chef d'atelier"})
    assert response.status_code == 200
    assert response.json()["first_name"] == "Paul-Henri" and response.json()["last_name"] == "Ngono"
    entry = next(a for a in client.get("/api/audit", headers=admin).json() if a["action"] == "employee.update")
    assert entry["detail"]["before"] == {"first_name": "Paul", "job_title": None}
    assert entry["detail"]["after"] == {"first_name": "Paul-Henri", "job_title": "Chef d'atelier"}


def test_edit_refuses_duplicate_matricule_and_archived_employee(client, admin, world):
    client.post("/api/employees", headers=admin, json={"matricule": "EMP-0001", "last_name": "A", "first_name": "B"})
    url = f"/api/employees/{world['employee']['id']}"
    assert client.patch(url, headers=admin, json={"matricule": "EMP-0001"}).status_code == 409
    archive(client, admin, world["employee"]["id"])
    assert client.patch(url, headers=admin, json={"first_name": "X"}).status_code == 400


def test_lists_hide_archived_people_and_filter_by_status(client, admin, world):
    client.post("/api/employees", headers=admin,
                json={"matricule": "EMP-0002", "last_name": "Bella", "first_name": "Awa"})
    archive(client, admin, world["employee"]["id"])

    def matricules(q=""):
        return {e["matricule"] for e in client.get(f"/api/employees{q}", headers=admin).json()}

    assert matricules() == {"EMP-0002"}
    assert matricules("?status=ARCHIVE") == {"EMP-0042"}
    assert matricules("?status=ACTIF") == {"EMP-0002"}
    assert matricules("?status=SUSPENDU") == set()


def test_rh_can_suspend_and_reactivate(client, make_user, world):
    rh = make_user("rh1", "rh")
    url = f"/api/employees/{world['employee']['id']}/status"
    assert client.patch(url, headers=rh, json={"status": "SUSPENDU"}).json()["status"] == "SUSPENDU"
    assert client.patch(url, headers=rh, json={"status": "ACTIF"}).json()["status"] == "ACTIF"
