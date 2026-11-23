"""Tâche 37: custom roles (FR-07) and the catalogue of actions grouped by theme (FR-05)."""
import re
from pathlib import Path

from app.domain.permissions import PERMISSION_CATALOGUE, Permission


def roles(client, admin):
    return {r["label"]: r for r in client.get("/api/roles", headers=admin).json()}


def create(client, headers, label, permissions):
    return client.post("/api/roles", headers=headers, json={"label": label, "permissions": permissions})


def test_catalogue_lists_every_action_once_grouped_by_theme(client, admin, agent):
    groups = client.get("/api/permissions", headers=admin).json()
    assert [g["theme"] for g in groups] == ["Employés", "Badges et accès", "Zones", "Terrain", "Consultation",
                                            "Administration"]
    codes = [p["code"] for g in groups for p in g["permissions"]]
    assert sorted(codes) == sorted(p.value for p in Permission) and len(codes) == 23
    assert {"code": "badges.revoke", "label": "Révoquer un badge"} in groups[1]["permissions"]
    assert client.get("/api/permissions", headers=agent).status_code == 403


def test_the_screen_shows_the_same_catalogue_as_the_server():
    """frontend/src/lib/permissions.ts mirrors PERMISSION_CATALOGUE: same themes, same order."""
    source = (Path(__file__).parents[2] / "frontend" / "src" / "lib" / "permissions.ts").read_text(encoding="utf-8")
    themes = re.findall(r'title: tx\("([^"]+)"\)', source)
    keys = re.findall(r'key: "([a-z._]+)"', source)
    assert themes == [theme for theme, _ in PERMISSION_CATALOGUE]
    assert keys == [p.value for _, items in PERMISSION_CATALOGUE for p, _ in items]


def test_create_rename_and_delete_a_custom_role(client, admin, make_user):
    created = create(client, admin, "  Chef   d'équipe ", ["logs.view", "reports.view"])
    assert created.status_code == 201
    role = created.json()
    assert (role["label"], role["name"], role["is_template"], role["users"]) == (
        "Chef d'équipe", "chef_d_equipe", False, 0)
    assert list(roles(client, admin))[:4] == ["Super admin", "Super user", "RH", "Agent"]  # templates first
    assert create(client, admin, "chef D'ÉQUIPE", []).status_code == 409

    # someone holding it gets exactly its rights
    chef = make_user("chef1", "chef_d_equipe")
    assert client.get("/api/logs", headers=chef).status_code == 200
    assert client.get("/api/employees", headers=chef).status_code == 403
    assert roles(client, admin)["Chef d'équipe"]["users"] == 1

    renamed = client.patch(f"/api/roles/{role['id']}", headers=admin, json={"label": "Chef de quart"})
    assert renamed.json()["label"] == "Chef de quart" and renamed.json()["users"] == 1
    assert client.patch(f"/api/roles/{role['id']}", headers=admin, json={"label": "RH"}).status_code == 409

    in_use = client.delete(f"/api/roles/{role['id']}", headers=admin)
    assert in_use.status_code == 409 and "autre rôle" in in_use.json()["detail"]
    chef_id = next(u["id"] for u in client.get("/api/users", headers=admin).json() if u["username"] == "chef1")
    rh = roles(client, admin)["RH"]
    assert client.put(f"/api/users/{chef_id}/role", headers=admin, json={"role_id": rh["id"]}).status_code == 200
    assert client.delete(f"/api/roles/{role['id']}", headers=admin).status_code == 204
    assert "Chef de quart" not in roles(client, admin)

    actions = [a["action"] for a in client.get("/api/audit?action=role", headers=admin).json()]
    assert actions == ["role.delete", "role.rename", "role.create"]


def test_template_roles_stay_and_rights_cannot_be_escalated(client, admin, make_user):
    rh = roles(client, admin)["RH"]
    assert client.patch(f"/api/roles/{rh['id']}", headers=admin, json={"label": "Ressources"}).status_code == 400
    assert client.delete(f"/api/roles/{rh['id']}", headers=admin).status_code == 400
    assert create(client, admin, "   ", []).status_code == 400

    # a role manager without data.purge cannot create a role that has it
    create(client, admin, "Gestion des rôles", ["roles.manage", "roles.assign", "logs.view"])
    manager = make_user("gr1", "gestion_des_roles")
    assert create(client, manager, "Purgeurs", ["data.purge"]).status_code == 403
    assert create(client, manager, "Lecteurs", ["logs.view"]).status_code == 201
    super_user = make_user("su1", "super_user")  # roles.manage is reserved to the super admin
    assert create(client, super_user, "Autre", []).status_code == 403
