"""Tâche 26: temporary access (dates) and weekly time slots, checked at the gate in Douala time."""
from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

import pytest

from app.domain.access_window import Slot, WindowRefusal, check, describe, describe_days

DOUALA = ZoneInfo("Africa/Douala")  # UTC+1, no daylight saving
WEEKDAYS = (1, 2, 3, 4, 5)


def local(y, m, d, hh, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=DOUALA)


# --- pure rules -------------------------------------------------------------------
@pytest.mark.parametrize(("moment", "expected"), [
    (local(2026, 11, 11, 7, 0), None),            # Wednesday 07:00, start included
    (local(2026, 11, 11, 17, 59), None),
    (local(2026, 11, 11, 18, 0), WindowRefusal.OUTSIDE_HOURS),  # end excluded
    (local(2026, 11, 11, 6, 59), WindowRefusal.OUTSIDE_HOURS),
    (local(2026, 11, 14, 10, 0), WindowRefusal.OUTSIDE_HOURS),  # Saturday
])
def test_day_slot(moment, expected):
    assert check(moment, DOUALA, None, None, [Slot(WEEKDAYS, time(7), time(18))]) == expected


@pytest.mark.parametrize(("moment", "expected"), [
    (local(2026, 11, 13, 23, 0), None),           # Friday night
    (local(2026, 11, 14, 5, 30), None),           # ... until Saturday morning
    (local(2026, 11, 14, 23, 0), WindowRefusal.OUTSIDE_HOURS),  # Saturday night: not ticked
    (local(2026, 11, 16, 5, 30), WindowRefusal.OUTSIDE_HOURS),  # Monday morning: Sunday not ticked
    (local(2026, 11, 16, 12, 0), WindowRefusal.OUTSIDE_HOURS),
])
def test_night_slot_crosses_midnight(moment, expected):
    assert check(moment, DOUALA, None, None, [Slot(WEEKDAYS, time(22), time(6))]) == expected


def test_whole_day_slot_and_several_slots():
    saturday = [Slot((6,), time(0), time(0))]
    assert check(local(2026, 11, 14, 3, 0), DOUALA, None, None, saturday) is None
    two = [Slot(WEEKDAYS, time(7), time(12)), Slot(WEEKDAYS, time(14), time(18))]
    assert check(local(2026, 11, 11, 13, 0), DOUALA, None, None, two) == WindowRefusal.OUTSIDE_HOURS
    assert check(local(2026, 11, 11, 15, 0), DOUALA, None, None, two) is None


def test_dates_and_gate_time_zone():
    start, end = local(2026, 11, 15, 0, 0), local(2026, 11, 30, 23, 59)
    assert check(local(2026, 11, 14, 23, 59), DOUALA, start, end, []) == WindowRefusal.NOT_YET
    assert check(local(2026, 11, 20, 12, 0), DOUALA, start, end, []) is None
    assert check(local(2026, 12, 1, 0, 0), DOUALA, start, end, []) == WindowRefusal.EXPIRED
    # 06:30 UTC is 07:30 at the gate: inside a 07:00-18:00 slot.
    utc = datetime(2026, 11, 11, 6, 30, tzinfo=UTC)
    assert check(utc, DOUALA, None, None, [Slot(WEEKDAYS, time(7), time(18))]) is None


def test_readable_summary():
    assert describe_days(WEEKDAYS) == "lun–ven" and describe_days((1, 3, 5)) == "lun, mer, ven"
    assert describe_days(range(1, 8)) == "tous les jours"
    text = describe(local(2026, 11, 15, 0), local(2026, 11, 30, 23, 59),
                    [Slot(WEEKDAYS, time(7), time(18)), Slot((6,), time(8), time(8))], DOUALA)
    assert text == "du 15/11/2026 au 30/11/2026 · lun–ven 07:00–18:00 · sam toute la journée"


# --- API + scan -------------------------------------------------------------------
def scan(client, headers, checkpoint, token):
    return client.post("/api/scan", headers=headers, json={"checkpoint_id": checkpoint["id"], "token": token}).json()


def relogin(client):
    """Sessions last 8 h: after moving the clock by days, sign the agent in again."""
    from tests.conftest import _login
    return _login(client, "agent1", "pw")


def restrict(client, admin, world, **body):
    url = f"/api/employees/{world['employee']['id']}/access/{world['zone']['id']}/restrictions"
    return client.put(url, headers=admin, json=body)


def test_outside_hours_entry_is_refused_with_a_clear_reason_exit_still_works(client, agent, admin, world, clock):
    # FakeClock: Wednesday 11/11/2026 08:00 UTC = 09:00 in Douala.
    weekdays = {"weekdays": [1, 2, 3, 4, 5], "start": "10:00", "end": "18:00"}
    response = restrict(client, admin, world, schedules=[weekdays])
    assert response.status_code == 200, response.text
    assert response.json()["restrictions"] == "lun–ven 10:00–18:00" and response.json()["usable_now"] is False
    refused = scan(client, agent, world["entry"], world["token"])
    assert refused["verdict"] == "REFUSE_ZONE"
    assert refused["detail"] == "Hors des horaires autorisés : lun–ven 10:00–18:00"
    line = client.get("/api/logs?limit=1", headers=admin).json()[0]
    assert line["reason"] == "hors_horaire"
    clock.advance(hours=1, minutes=5)  # 10:05
    assert scan(client, agent, world["entry"], world["token"])["verdict"] == "AUTORISE"
    clock.advance(hours=9)  # 19:05: still inside, the exit is never blocked
    assert scan(client, relogin(client), world["exit"], world["token"])["verdict"] == "SORTIE_ENREGISTREE"


def test_temporary_access_by_dates(client, agent, admin, world, clock):
    restrict(client, admin, world, valid_from="2026-11-12T00:00:00+01:00", valid_until="2026-11-13T23:59:59+01:00")
    assert scan(client, agent, world["entry"], world["token"])["detail"] == "Accès pas encore valable"
    clock.advance(days=1)
    agent = relogin(client)
    assert scan(client, agent, world["entry"], world["token"])["verdict"] == "AUTORISE"
    scan(client, agent, world["exit"], world["token"])
    clock.advance(days=2)
    expired = scan(client, relogin(client), world["entry"], world["token"])
    assert expired["verdict"] == "REFUSE_ZONE" and expired["detail"] == "Accès à cette zone expiré"


def test_access_screen_shows_restrictions_and_audit_keeps_before_after(client, admin, world):
    restrict(client, admin, world, valid_until="2026-11-30T23:59:59+01:00",
             schedules=[{"weekdays": [6], "start": "06:00", "end": "10:00"}])
    access = client.get(f"/api/employees/{world['employee']['id']}/access", headers=admin).json()
    zone = next(z for u in access for z in u["zones"] if z["id"] == world["zone"]["id"])
    assert zone["restrictions"] == "jusqu'au 30/11/2026 · sam 06:00–10:00"
    assert zone["schedules"] == [{"weekdays": [6], "start": "06:00:00", "end": "10:00:00"}]
    restrict(client, admin, world)  # back to permanent
    line = client.get("/api/audit?action=authorization.restrict", headers=admin).json()[0]
    assert line["summary"] == "Restrictions : jusqu'au 30/11/2026 · sam 06:00–10:00 → permanent ; Zone : Usine"


def test_validation(client, admin, world):
    assert restrict(client, admin, world, valid_from="2026-11-20T00:00:00+01:00",
                    valid_until="2026-11-10T00:00:00+01:00").status_code == 400
    slot = {"start": "07:00", "end": "09:00"}
    assert restrict(client, admin, world, schedules=[{**slot, "weekdays": [8]}]).status_code == 400
    assert restrict(client, admin, world, schedules=[{**slot, "weekdays": []}]).status_code == 422
    assert restrict(client, admin, world, valid_until="2026-11-30T23:59:59").status_code == 422  # time zone required
    other = client.post("/api/zones", headers=admin, json={"name": "Quai"}).json()
    url = f"/api/employees/{world['employee']['id']}/access/{other['id']}/restrictions"
    assert client.put(url, headers=admin, json={}).status_code == 404  # zone not ticked


def test_unticking_a_zone_drops_its_slots_and_kept_zones_keep_them(client, admin, world):
    restrict(client, admin, world, schedules=[{"weekdays": [1], "start": "07:00", "end": "09:00"}])
    other = client.post("/api/zones", headers=admin, json={"name": "Quai"}).json()
    employee = world["employee"]["id"]
    both = {"zone_ids": [world["zone"]["id"], other["id"]]}
    client.put(f"/api/employees/{employee}/access", headers=admin, json=both)
    access = client.get(f"/api/employees/{employee}/access", headers=admin).json()
    usine = next(z for u in access for z in u["zones"] if z["id"] == world["zone"]["id"])
    assert usine["restrictions"] == "lun 07:00–09:00"
    client.put(f"/api/employees/{employee}/access", headers=admin, json={"zone_ids": [other["id"]]})
    client.put(f"/api/employees/{employee}/access", headers=admin, json={"zone_ids": [world["zone"]["id"]]})
    access = client.get(f"/api/employees/{employee}/access", headers=admin).json()
    assert next(z for u in access for z in u["zones"] if z["id"] == world["zone"]["id"])["restrictions"] == ""
    assert client.delete(f"/api/zones/{other['id']}", headers=admin).status_code == 204  # no orphan slot left
