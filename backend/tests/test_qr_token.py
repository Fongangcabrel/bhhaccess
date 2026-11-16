"""Compact QR token (tâches 8-9): smaller QR, same security, old printed badges still read."""
import base64
from datetime import UTC, datetime

import pytest
import qrcode
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.core.exceptions import InvalidTokenError
from app.domain.qr_token import Ed25519TokenSigner

NOW = datetime(2026, 11, 12, 8, 0, tzinfo=UTC)


def new_pem() -> str:
    return Ed25519PrivateKey.generate().private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()


@pytest.fixture
def signer():
    return Ed25519TokenSigner(new_pem(), "bhhaccess")


def qr_version(data: str) -> int:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H)
    qr.add_data(data)
    qr.make(fit=True)
    return qr.version


def test_compact_token_round_trip_and_size(signer):
    token = signer.sign(123456, 7, NOW)
    assert token.startswith("B1") and len(token) == 114
    assert token == token.upper()  # QR alphanumeric mode
    claims = signer.verify(token)
    assert (claims.badge_id, claims.version) == (123456, 7)
    assert qr_version(token) <= 8 < qr_version(signer.sign_jwt(123456, 7, NOW))


def test_old_jwt_badges_still_read(signer):
    claims = signer.verify(signer.sign_jwt(42, 3, NOW))
    assert (claims.badge_id, claims.version) == (42, 3)


def test_tampered_compact_token_is_refused(signer):
    token = signer.sign(42, 1, NOW)
    raw = bytearray(base64.b32decode(token[2:] + "=" * (-len(token[2:]) % 8)))
    raw[1] ^= 0x01  # change the badge id, keep the signature
    forged = "B1" + base64.b32encode(bytes(raw)).decode().rstrip("=")
    for bad in (forged, token[:-1], token + "A", "B1" + "A" * 112, "B1" + "!" * 112, "B1", ""):
        with pytest.raises(InvalidTokenError):
            signer.verify(bad)


def test_other_key_or_issuer_is_refused():
    pem = new_pem()
    token = Ed25519TokenSigner(pem, "bhhaccess").sign(42, 1, NOW)
    with pytest.raises(InvalidTokenError):
        Ed25519TokenSigner(new_pem(), "bhhaccess").verify(token)  # other key
    with pytest.raises(InvalidTokenError):
        Ed25519TokenSigner(pem, "autre").verify(token)  # same key, other issuer


def test_scan_reads_both_formats(client, agent, admin, world, app):
    signer = app.state.signer
    assert world["token"].startswith("B1")  # badges issued now are compact
    old = signer.sign_jwt(world["badge"]["id"], world["badge"]["version"], NOW)
    response = client.post("/api/scan", headers=agent, json={"checkpoint_id": world["entry"]["id"], "token": old})
    assert response.json()["verdict"] == "AUTORISE"


def test_qr_image_uses_the_compact_token(client, admin, world):
    png = client.get(f"/api/badges/{world['badge']['id']}/qr.png", headers=admin)
    assert png.status_code == 200 and png.headers["content-type"] == "image/png"
