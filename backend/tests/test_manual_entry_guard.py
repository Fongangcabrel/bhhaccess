"""Tâche 39: typed matricules are journalised and limited; only a super admin handles a super admin."""
from tests.conftest import _login
from tests.test_units_devices_agents import _pair


def typed(client, headers, checkpoint, matricule, device=True):
    path = "/api/device/scan/manual" if device else "/api/scan/manual"
    return client.post(path, headers=headers, json={"checkpoint_id": checkpoint["id"], "matricule": matricule})


def test_unknown_or_badgeless_matricule_reads_as_unrecognised_and_is_journalised(client, admin, world):
    _, phone = _pair(client, admin)
    unknown = typed(client, phone, world["entry"], " EMP-9999 ")
    assert unknown.status_code == 200
    assert unknown.json()["verdict"] == "REFUSE_INVALIDE" and unknown.json()["employee"] is None

    client.post(f"/api/badges/{world['badge']['id']}/revoke", headers=admin, json={"reason": "PERTE"})
    no_badge = typed(client, phone, world["entry"], "EMP-0042").json()
    assert no_badge["verdict"] == "REFUSE_INVALIDE" and no_badge["employee"] is None  # same answer: nothing learnt

    badgeless, unknown_line = client.get("/api/logs?method=MANUEL", headers=admin).json()
    assert unknown_line["reason"] == "matricule_inconnu (saisie manuelle) : EMP-9999"
    assert unknown_line["employee_name"] is None and unknown_line["device_name"] == "Tel Poste 1"
    assert badgeless["reason"] == "aucun_badge_actif (saisie manuelle)" and badgeless["employee_name"] == "Paul Ngono"


def test_five_failures_block_typing_on_that_phone_for_a_while(client, admin, world, clock):
    _, phone = _pair(client, admin)
    _, other = _pair(client, admin, "Tel Poste 2")
    for n in range(5):
        assert typed(client, phone, world["entry"], f"X-{n}").status_code == 200
    blocked = typed(client, phone, world["entry"], "EMP-0042")  # even a right matricule, while blocked
    assert blocked.status_code == 429 and "Trop de tentatives" in blocked.json()["detail"]
    assert typed(client, other, world["entry"], "EMP-0042").json()["verdict"] == "AUTORISE"  # other phone fine
    assert len(client.get("/api/logs?method=MANUEL&limit=50", headers=admin).json()) == 6  # the blocked try: none

    clock.advance(minutes=11)
    assert typed(client, phone, world["entry"], "EMP-0042").status_code == 200


def test_a_logged_in_agent_is_limited_too(client, agent, world):
    for n in range(5):
        typed(client, agent, world["entry"], f"X-{n}", device=False)
    assert typed(client, agent, world["entry"], "EMP-0042", device=False).status_code == 429


def test_only_a_super_admin_handles_a_super_admin_account(client, admin, make_user):
    make_user("rh1", "rh")
    make_user("deleg", "super_user")
    users = {u["username"]: u["id"] for u in client.get("/api/users", headers=admin).json()}
    for permission in ("users.manage", "roles.assign"):
        client.put(f"/api/users/{users['deleg']}/overrides", headers=admin,
                   json={"permission": permission, "effect": "allow"})
    deleg = _login(client, "deleg", "pw")
    target = users["admin"]
    rh_role = next(r["id"] for r in client.get("/api/roles", headers=admin).json() if r["name"] == "rh")
    refused = [
        client.patch(f"/api/users/{target}/active", headers=deleg, json={"is_active": False}),
        client.post(f"/api/users/{target}/password", headers=deleg, json={"new_password": "Reprise-2026"}),
        client.put(f"/api/users/{target}/role", headers=deleg, json={"role_id": rh_role}),
        client.put(f"/api/users/{target}/overrides", headers=deleg, json={"permission": "logs.view", "effect": "deny"}),
    ]
    assert [r.status_code for r in refused] == [403, 403, 403, 403]
    assert "Seul un super admin" in refused[0].json()["detail"]
    # the same delegate still manages ordinary accounts
    ordinary = client.patch(f"/api/users/{users['rh1']}/active", headers=deleg, json={"is_active": False})
    assert ordinary.status_code == 200
