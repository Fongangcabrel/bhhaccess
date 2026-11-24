"""Messages in the language the app asks for (Accept-Language); French by default."""
from app.core.i18n import EN
from tests.test_units_devices_agents import _pair


def test_errors_follow_the_app_language(client):
    fr = client.post("/api/device/pair", json={"code": "ZZZZ9999"})
    en = client.post("/api/device/pair", json={"code": "ZZZZ9999"}, headers={"Accept-Language": "en-GB,en;q=0.9"})
    assert fr.json()["detail"] == "Code invalide ou expiré"
    assert en.status_code == 401 and en.json()["detail"] == "Invalid or expired code"


def test_refusal_detail_is_translated(client, admin, world):
    url = f"/api/employees/{world['employee']['id']}/access/{world['zone']['id']}/restrictions"
    client.put(url, headers=admin, json={"schedules": [{"weekdays": [6], "start": "08:00", "end": "12:00"}]})
    _, device = _pair(client, admin)
    body = {"checkpoint_id": world["entry"]["id"], "token": world["token"]}
    out = client.post("/api/device/scan", headers={**device, "Accept-Language": "en"}, json=body).json()
    assert out["verdict"] == "REFUSE_ZONE" and out["detail"] == "Outside the allowed hours: Sat 08:00–12:00"


def test_every_translation_is_a_real_message():
    assert all(fr and en and fr != en for fr, en in EN.items())


def test_every_error_message_has_an_english_text():
    """Each message raised to the screens (DomainError and subclasses) is translated."""
    import ast
    import pathlib

    from app.core.i18n import tr

    internal = {"QR key must be an Ed25519 private key", "QR key must be an Ed25519 key",  # start-up only
                "badge id or version out of range for the compact QR",
                "naive datetime not allowed"}
    missing = []
    for path in pathlib.Path("app").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not (isinstance(node, ast.Call) and getattr(node.func, "id", "").endswith("Error") and node.args):
                continue
            arg = node.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                message = arg.value
            elif isinstance(arg, ast.JoinedStr):
                message = "".join(v.value if isinstance(v, ast.Constant) else "X" for v in arg.values)
            else:
                continue
            if message not in internal and tr(message, "en") == message:
                missing.append(f"{path}: {message}")
    assert missing == []
