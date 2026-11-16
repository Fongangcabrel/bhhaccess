"""One agent at a single door (entry + exit) and rotation between posts (tâche 11)."""


def new_agent(client, admin, name="Jean Ekané"):
    return client.post("/api/agents", headers=admin, json={"full_name": name}).json()


def place(client, admin, checkpoint, agent_id, keep=False):
    response = client.put(f"/api/checkpoints/{checkpoint['id']}/agent", headers=admin,
                          json={"agent_id": agent_id, "keep_other_posts": keep})
    assert response.status_code == 204, response.text


def posts_of(client, admin, agent_id):
    found = next(a for a in client.get("/api/agents", headers=admin).json() if a["id"] == agent_id)
    return {p["checkpoint_name"] for p in found["posts"]}


def scan(client, agent, checkpoint, token):
    return client.post("/api/scan", headers=agent,
                       json={"checkpoint_id": checkpoint["id"], "token": token}).json()


def test_one_agent_holds_entry_and_exit_of_a_single_door(client, admin, agent, world):
    jean = new_agent(client, admin)
    place(client, admin, world["entry"], jean["id"])
    place(client, admin, world["exit"], jean["id"], keep=True)
    assert posts_of(client, admin, jean["id"]) == {"Entrée usine", "Sortie usine"}

    # Both directions are attributed to the same person in the journal.
    scan(client, agent, world["entry"], world["token"])
    scan(client, agent, world["exit"], world["token"])
    names = {line["agent_name"] for line in client.get("/api/logs", headers=admin).json()}
    assert names == {"Jean Ekané"}


def test_rotation_moves_the_agent_and_keeps_history(client, admin, world):
    jean = new_agent(client, admin)
    place(client, admin, world["entry"], jean["id"])
    place(client, admin, world["exit"], jean["id"])  # default: move
    assert posts_of(client, admin, jean["id"]) == {"Sortie usine"}
    history = client.get(f"/api/assignments?agent_id={jean['id']}", headers=admin).json()
    assert [(h["checkpoint_name"], h["ended_at"] is None) for h in history] == [
        ("Sortie usine", True), ("Entrée usine", False)]


def test_a_post_keeps_a_single_agent(client, admin, world):
    jean, marie = new_agent(client, admin), new_agent(client, admin, "Marie Ndi")
    place(client, admin, world["entry"], jean["id"])
    place(client, admin, world["exit"], jean["id"], keep=True)
    place(client, admin, world["entry"], marie["id"])  # Marie takes the entry over
    assert posts_of(client, admin, jean["id"]) == {"Sortie usine"}
    assert posts_of(client, admin, marie["id"]) == {"Entrée usine"}
    audit = [a for a in client.get("/api/audit?limit=500", headers=admin).json() if a["action"] == "agent.assign"]
    assert audit[0]["detail"]["replaced"] == "Jean Ekané"


def test_deactivating_an_agent_frees_every_post(client, admin, world):
    jean = new_agent(client, admin)
    place(client, admin, world["entry"], jean["id"])
    place(client, admin, world["exit"], jean["id"], keep=True)
    client.patch(f"/api/agents/{jean['id']}/active", headers=admin, json={"is_active": False})
    assert posts_of(client, admin, jean["id"]) == set()
    assert all(c["agent_id"] is None for c in client.get("/api/checkpoints", headers=admin).json())
