"""Tâche 35: the same badge read again at the same post within 3 s is one passage (server side)."""


def scan(client, headers, checkpoint, token):
    response = client.post("/api/scan", headers=headers, json={"checkpoint_id": checkpoint["id"], "token": token})
    assert response.status_code == 200, response.text
    return response.json()


def journal(client, admin):
    return client.get("/api/logs?limit=50", headers=admin).json()


def test_a_repeat_within_3_s_gives_the_first_answer_and_records_nothing(client, agent, admin, world, clock):
    first = scan(client, agent, world["entry"], world["token"])
    clock.advance(seconds=1)
    again = scan(client, agent, world["entry"], world["token"])
    assert first["verdict"] == again["verdict"] == "AUTORISE"  # not « déjà entré » (strict zone)
    assert again["log_id"] == first["log_id"] and again["repeat"] is True and first["repeat"] is False
    assert again["employee"]["matricule"] == "EMP-0042" and again["occurred_at"] == first["occurred_at"]
    assert len(journal(client, admin)) == 1
    assert len(client.get("/api/presence", headers=admin).json()) == 1

    clock.advance(seconds=3)  # 4 s after the first scan: a real second passage
    later = scan(client, agent, world["entry"], world["token"])
    assert later["verdict"] == "REFUSE_ANTIPASSBACK" and later["repeat"] is False
    assert len(journal(client, admin)) == 2


def test_exactly_3_s_later_is_a_new_passage(client, agent, admin, world, clock):
    scan(client, agent, world["entry"], world["token"])
    clock.advance(seconds=3)
    assert scan(client, agent, world["entry"], world["token"])["repeat"] is False
    assert len(journal(client, admin)) == 2


def test_another_post_or_a_typed_matricule(client, agent, admin, world, clock):
    scan(client, agent, world["entry"], world["token"])
    out = scan(client, agent, world["exit"], world["token"])  # other post, same instant: a real exit
    assert out["verdict"] == "SORTIE_ENREGISTREE" and out["repeat"] is False
    typed = client.post("/api/scan/manual", headers=agent,
                        json={"checkpoint_id": world["exit"]["id"], "matricule": "EMP-0042"}).json()
    assert typed["repeat"] is True and typed["log_id"] == out["log_id"]  # same badge at the same post
    assert len(journal(client, admin)) == 2


def test_a_repeated_refusal_keeps_its_details_without_a_new_alert(client, agent, admin, world, clock):
    scan(client, agent, world["entry"], world["token"])
    clock.advance(seconds=10)
    refused = scan(client, agent, world["entry"], world["token"])
    clock.advance(seconds=2)
    again = scan(client, agent, world["entry"], world["token"])
    assert again["verdict"] == "REFUSE_ANTIPASSBACK" and again["repeat"] is True
    assert again["last_entry_at"] == refused["last_entry_at"] is not None
    assert again["last_entry_checkpoint"] == "Entrée usine"
    for _ in range(6):  # a camera stuck on the badge: no burst alert, one line
        scan(client, agent, world["entry"], world["token"])
    assert len(journal(client, admin)) == 2
    assert client.get("/api/alerts?type=RAFALE", headers=admin).json() == []


def test_an_archived_badge_repeated_stays_anonymous_and_is_alerted_once(client, agent, admin, world, clock):
    client.post(f"/api/employees/{world['employee']['id']}/archive", headers=admin, json={"reason": "Départ"})
    first = scan(client, agent, world["entry"], world["token"])
    clock.advance(seconds=1)
    again = scan(client, agent, world["entry"], world["token"])
    assert again["verdict"] == "REFUSE_INVALIDE" and again["employee"] is None and again["repeat"] is True
    assert again["log_id"] == first["log_id"] and len(journal(client, admin)) == 1
    assert len(client.get("/api/alerts?type=EMPLOYE_ARCHIVE", headers=admin).json()) == 1
