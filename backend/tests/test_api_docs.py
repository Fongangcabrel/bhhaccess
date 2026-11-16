"""/docs stays in step with the code: every route documented in French, rights read from the guards."""
from app import api_docs


def test_every_route_is_documented_and_no_entry_is_stale(client):
    routes = api_docs.documented_routes(client.app)
    keys = {key for path, route in routes for key in api_docs.route_keys(path, route)}
    assert len(keys) > 90
    missing = sorted(keys - api_docs.ROUTES.keys())
    stale = sorted(api_docs.ROUTES.keys() - keys)
    assert not missing, f"Routes sans documentation dans app/api_docs.py : {missing}"
    assert not stale, f"Entrées de app/api_docs.py sans route : {stale}"
    sections = {tag["name"] for tag in api_docs.TAGS}
    assert {tag for tag, _, _ in api_docs.ROUTES.values()} <= sections


def test_openapi_shows_sections_summaries_and_rights(client):
    schema = client.get("/openapi.json").json()
    assert schema["info"]["title"] == "BHHaccess – API"
    assert [t["name"] for t in schema["tags"]][:3] == ["Connexion", "Tableau de bord", "Employés"]
    ack = schema["paths"]["/api/alerts/{alert_id}/revoke-badge"]["post"]
    assert ack["tags"] == ["Alertes"] and ack["summary"] == "Révoquer le badge depuis l'alerte"
    assert "`reports.view` + `badges.revoke`" in ack["description"]
    export = schema["paths"]["/api/exports/journal.{fmt}"]["get"]
    assert "`logs.view` + `data.export`" in export["description"]
    phone = schema["paths"]["/api/device/scan"]["post"]
    assert "téléphone appairé" in phone["description"]
    assert "public" in schema["paths"]["/api/auth/login"]["post"]["description"]
    assert "toute personne connectée" in schema["paths"]["/api/auth/me"]["get"]["description"]
    assert schema["paths"]["/api/org/entities"]["get"]["tags"] == ["Entités et départements"]
