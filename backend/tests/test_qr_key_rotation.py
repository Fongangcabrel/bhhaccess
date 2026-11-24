"""Tâche 43: the QR carries a key id, so the signing key can be replaced without reprinting at once."""
import base64
from datetime import UTC, datetime

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.core.exceptions import InvalidTokenError
from app.domain.qr_token import Ed25519TokenSigner

NOW = datetime(2026, 11, 24, 8, 0, tzinfo=UTC)


def new_pem() -> str:
    return Ed25519PrivateKey.generate().private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()


def public_pem(private_pem: str) -> str:
    key = serialization.load_pem_private_key(private_pem.encode(), password=None)
    return key.public_key().public_bytes(serialization.Encoding.PEM,
                                         serialization.PublicFormat.SubjectPublicKeyInfo).decode()


def private_pem_of(signer: Ed25519TokenSigner) -> str:
    return signer._private.private_bytes(  # the key of the running app: tests only
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()


def test_former_key_still_reads_every_format():
    old_pem, new = new_pem(), new_pem()
    old = Ed25519TokenSigner(old_pem, "bhhaccess")
    printed = [old.sign(42, 3, NOW), old.sign_compact(42, 3, NOW), old.sign_jwt(42, 3, NOW)]
    for previous in (old_pem, public_pem(old_pem)):  # private or public PEM both accepted
        rotated = Ed25519TokenSigner(new, "bhhaccess", previous)
        assert rotated.key_ids() == [rotated.key_id, old.key_id] and rotated.key_id != old.key_id
        for token in printed:
            claims = rotated.verify(token)
            assert (claims.badge_id, claims.version) == (42, 3)
        assert rotated.sign(42, 3, NOW) != printed[0]  # new prints use the new key
    retired = Ed25519TokenSigner(new, "bhhaccess")  # former key removed from the configuration
    for token in printed:
        with pytest.raises(InvalidTokenError):
            retired.verify(token)


def test_key_id_is_signed():
    a, b = Ed25519TokenSigner(new_pem(), "bhhaccess"), Ed25519TokenSigner(new_pem(), "bhhaccess")
    both = Ed25519TokenSigner(new_pem(), "bhhaccess", private_pem_of(a) + private_pem_of(b))
    body = a.sign(42, 1, NOW)[2:]
    raw = bytearray(base64.b32decode(body + "=" * (-len(body) % 8)))
    raw[0:2] = bytes.fromhex(b.key_id)  # claim the other accepted key
    with pytest.raises(InvalidTokenError):
        both.verify("B2" + base64.b32encode(bytes(raw)).decode().rstrip("="))


def test_previous_keys_must_be_ed25519():
    with pytest.raises(ValueError):
        Ed25519TokenSigner(new_pem(), "bhhaccess", "-----BEGIN PUBLIC KEY-----\nAAAA\n-----END PUBLIC KEY-----")


def test_qr_keys_follow_the_reprints(client, admin, agent, world, app):
    assert client.get("/api/qr-keys", headers=agent).status_code == 403
    old = app.state.signer
    body = client.get("/api/qr-keys", headers=admin).json()
    assert body == {"keys": [{"key_id": old.key_id, "active": True, "badges": 1}], "untracked": 0,
                    "unknown_key": 0}

    # Key change: the former key stays accepted, the badge printed with it is still read.
    app.state.signer = Ed25519TokenSigner(new_pem(), "bhhaccess", private_pem_of(old))
    new_id = app.state.signer.key_id
    body = client.get("/api/qr-keys", headers=admin).json()
    assert body["keys"] == [{"key_id": new_id, "active": True, "badges": 0},
                            {"key_id": old.key_id, "active": False, "badges": 1}]
    scan = client.post("/api/scan", headers=agent, json={"checkpoint_id": world["entry"]["id"],
                                                         "token": world["token"]})
    assert scan.json()["verdict"] == "AUTORISE"

    # Reprint: the badge moves to the new key.
    reprinted = client.get(f"/api/badges/{world['badge']['id']}/qr-token", headers=admin).json()["token"]
    assert reprinted != world["token"]
    body = client.get("/api/qr-keys", headers=admin).json()
    assert [k["badges"] for k in body["keys"]] == [1, 0]

    # The former key is removed: the old print is refused, the reprint is read.
    app.state.signer = Ed25519TokenSigner(private_pem_of(app.state.signer), "bhhaccess")
    app.state.clock.advance(seconds=4)
    refused = client.post("/api/scan", headers=agent, json={"checkpoint_id": world["exit"]["id"],
                                                            "token": world["token"]})
    assert refused.json()["verdict"] == "REFUSE_INVALIDE"
    app.state.clock.advance(seconds=4)
    read = client.post("/api/scan", headers=agent, json={"checkpoint_id": world["exit"]["id"],
                                                         "token": reprinted})
    assert read.json()["verdict"] == "SORTIE_ENREGISTREE"


def test_badges_printed_with_a_removed_key_are_counted(client, admin, world, app):
    app.state.signer = Ed25519TokenSigner(new_pem(), "bhhaccess")  # former key dropped at once
    body = client.get("/api/qr-keys", headers=admin).json()
    assert body["unknown_key"] == 1 and body["keys"][0]["badges"] == 0
