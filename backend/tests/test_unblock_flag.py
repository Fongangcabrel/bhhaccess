"""Tâche 24: the DEBLOQUE flag goes on the scan that follows the unblock (TRD §9, App Flow 4.1)."""


def scan(client, headers, checkpoint, token):
    client.app.state.clock.advance(seconds=4)  # distinct passages: a repeat within 3 s counts once
    return client.post("/api/scan", headers=headers, json={"checkpoint_id": checkpoint["id"], "token": token}).json()


def unblock(client, admin, world, mode="sortie"):
    payload = {"employee_id": world["employee"]["id"], "zone_id": world["zone"]["id"],
               "reason": "Sorti sans scanner", "mode": mode}
    assert client.post("/api/presence/unblock", headers=admin, json=payload).status_code == 204


def journal(client, admin):
    return client.get("/api/logs?limit=50", headers=admin).json()  # newest first


def test_next_entry_after_unblock_is_flagged_not_the_unblock_line(client, agent, admin, world):
    scan(client, agent, world["entry"], world["token"])
    assert scan(client, agent, world["entry"], world["token"])["verdict"] == "REFUSE_ANTIPASSBACK"
    unblock(client, admin, world)
    console_line = journal(client, admin)[0]
    assert console_line["method"] == "CONSOLE" and console_line["flags"] == []
    assert console_line["reason"] == "Sorti sans scanner" and console_line["verdict"] == "SORTIE_ENREGISTREE"

    entry = scan(client, agent, world["entry"], world["token"])
    assert entry["verdict"] == "AUTORISE" and "DEBLOQUE" in entry["flags"]
    assert "DEBLOQUE" in journal(client, admin)[0]["flags"] and journal(client, admin)[0]["method"] == "QR"


def test_only_the_first_scan_through_gets_the_flag(client, agent, admin, world):
    scan(client, agent, world["entry"], world["token"])
    unblock(client, admin, world)
    scan(client, agent, world["entry"], world["token"])
    assert "DEBLOQUE" not in scan(client, agent, world["exit"], world["token"])["flags"]
    assert "DEBLOQUE" not in scan(client, agent, world["entry"], world["token"])["flags"]


def test_a_refusal_in_between_does_not_consume_the_flag(client, agent, admin, world):
    scan(client, agent, world["entry"], world["token"])
    unblock(client, admin, world, mode="sortie")
    client.put(f"/api/employees/{world['employee']['id']}/access", headers=admin, json={"zone_ids": []})
    assert scan(client, agent, world["entry"], world["token"])["verdict"] == "REFUSE_ZONE"
    client.put(f"/api/employees/{world['employee']['id']}/access", headers=admin,
               json={"zone_ids": [world["zone"]["id"]]})
    assert "DEBLOQUE" in scan(client, agent, world["entry"], world["token"])["flags"]


def test_manual_entry_unblock_flags_the_next_exit(client, agent, admin, world):
    unblock(client, admin, world, mode="entree")
    leave = scan(client, agent, world["exit"], world["token"])
    assert leave["verdict"] == "SORTIE_ENREGISTREE" and "DEBLOQUE" in leave["flags"]
    assert "SORTIE_SANS_ENTREE" not in leave["flags"]


def test_typed_matricule_is_recorded_as_manual(client, agent, admin, world):
    client.post("/api/scan/manual", headers=agent,
                json={"checkpoint_id": world["entry"]["id"], "matricule": "EMP-0042"})
    assert journal(client, admin)[0]["method"] == "MANUEL"


def test_journal_filters_by_flag_and_method(client, agent, admin, world):
    scan(client, agent, world["entry"], world["token"])
    unblock(client, admin, world)
    scan(client, agent, world["entry"], world["token"])  # DEBLOQUE
    scan(client, agent, world["exit"], world["token"])
    flagged = client.get("/api/logs?flag=DEBLOQUE", headers=admin).json()
    assert len(flagged) == 1 and flagged[0]["verdict"] == "AUTORISE"
    console = client.get("/api/logs?method=CONSOLE", headers=admin).json()
    assert len(console) == 1 and console[0]["reason"] == "Sorti sans scanner"
    assert client.get("/api/logs?flag=NIMPORTE", headers=admin).status_code == 422
    from io import BytesIO

    from openpyxl import load_workbook
    sheet = load_workbook(BytesIO(client.get("/api/exports/journal.xlsx?flag=DEBLOQUE",
                                             headers=admin).content)).active
    assert "Alerte : Après déblocage manuel" in sheet["A3"].value
    assert len(list(sheet.iter_rows(min_row=5, values_only=True))) == 1
