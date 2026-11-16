"""Badges (tâche 22): revocation reason, active employees only, one active badge per employee."""
import pytest
from sqlalchemy.exc import IntegrityError

from app.domain.enums import BadgeStatus
from app.models import Badge


def badges_of(client, admin, employee_id):
    return client.get(f"/api/employees/{employee_id}/badges", headers=admin).json()


def test_revoke_needs_a_reason_and_records_it(client, admin, world):
    url = f"/api/badges/{world['badge']['id']}/revoke"
    assert client.post(url, headers=admin, json={}).status_code == 422
    assert client.post(url, headers=admin, json={"reason": "AUTRE"}).status_code == 400  # needs a note
    assert client.post(url, headers=admin, json={"reason": "REMPLACEMENT"}).status_code == 400
    done = client.post(url, headers=admin, json={"reason": "VOL", "note": "  Volé au parking  "}).json()
    assert done["status"] == "REVOQUE" and done["revoked_reason"] == "VOL" and done["revoked_note"] == "Volé au parking"
    assert done["revoked_at"] is not None
    assert client.post(url, headers=admin, json={"reason": "PERTE"}).status_code == 409  # never twice
    audit = next(a for a in client.get("/api/audit?limit=500", headers=admin).json() if a["action"] == "badge.revoke")
    assert audit["target"] == "EMP-0042" and audit["detail"]["reason"] == "VOL"


def test_reissue_marks_the_old_badge_as_replaced(client, admin, world):
    employee_id = world["employee"]["id"]
    second = client.post("/api/badges", headers=admin, json={"employee_id": employee_id}).json()
    assert second["version"] == 2
    old, new = sorted(badges_of(client, admin, employee_id), key=lambda b: b["version"])
    assert old["status"] == "REVOQUE" and old["revoked_reason"] == "REMPLACEMENT"
    assert new["status"] == "ACTIF" and new["revoked_reason"] is None
    audit = [a for a in client.get("/api/audit?limit=500", headers=admin).json() if a["action"] == "badge.issue"]
    assert audit[0]["detail"]["replaced_versions"] == [1]


def test_badge_only_for_active_employees(client, admin, world):
    employee_id = world["employee"]["id"]
    client.patch(f"/api/employees/{employee_id}/status", headers=admin, json={"status": "SUSPENDU"})
    refused = client.post("/api/badges", headers=admin, json={"employee_id": employee_id})
    assert refused.status_code == 400 and "suspendu" in refused.json()["detail"].lower()
    client.patch(f"/api/employees/{employee_id}/status", headers=admin, json={"status": "ACTIF"})
    assert client.post("/api/badges", headers=admin, json={"employee_id": employee_id}).status_code == 201


def test_expiry_in_the_past_is_refused(client, admin, world):
    body = {"employee_id": world["employee"]["id"], "expires_at": "2020-01-01T00:00:00Z"}
    assert client.post("/api/badges", headers=admin, json=body).status_code == 400


def test_archiving_revokes_with_departure_reason(client, admin, world):
    employee_id = world["employee"]["id"]
    client.post(f"/api/employees/{employee_id}/archive", headers=admin, json={"reason": "Fin de contrat"})
    (badge,) = badges_of(client, admin, employee_id)
    assert badge["revoked_reason"] == "DEPART" and badge["revoked_note"] == "Archivage : Fin de contrat"


def test_database_refuses_two_active_badges(app, clock, world):
    """Even code that forgets to revoke cannot create a second active badge (index one_active_badge)."""
    with app.state.session_factory() as session:
        session.add(Badge(employee_id=world["employee"]["id"], version=9, status=BadgeStatus.ACTIVE,
                          issued_at=clock.now()))
        with pytest.raises(IntegrityError):
            session.flush()
