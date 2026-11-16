"""Badge QR token: signed with Ed25519, permanent, and carrying no personal data.

Two formats are read; new badges get the compact one.

* Compact (``B1`` + base32): badge id (4 bytes) + version (2 bytes) + Ed25519 signature
  (64 bytes) = 114 characters, all in the QR "alphanumeric" set. With error correction H
  that is a version-8 QR (49 modules) instead of version 15 (77 modules) for the JWT: much
  bigger modules at the same 4 cm print size, so phones read it faster, logo included.
* JWT (EdDSA): the original format, still accepted so already printed badges keep working.

Depends on the ``TokenSigner`` abstraction so the algorithm can change without touching callers.
"""
import base64
import binascii
import struct
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

import jwt
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.core.exceptions import InvalidTokenError

COMPACT_PREFIX = "B1"
_PAYLOAD = struct.Struct(">IH")  # badge id (uint32), version (uint16)
_SIGNATURE_SIZE = 64
_COMPACT_LENGTH = len(COMPACT_PREFIX) + (_PAYLOAD.size + _SIGNATURE_SIZE) * 8 // 5  # 114


@dataclass(frozen=True)
class QrClaims:
    badge_id: int
    version: int


class TokenSigner(Protocol):
    def sign(self, badge_id: int, version: int, issued_at: datetime) -> str: ...
    def verify(self, token: str) -> QrClaims: ...


class Ed25519TokenSigner:
    def __init__(self, private_key_pem: str, issuer: str) -> None:
        self._issuer = issuer
        # Domain separation: a compact signature is only valid for this issuer and this format.
        self._context = f"{issuer}|badge-qr|v1|".encode()
        if private_key_pem:
            key = serialization.load_pem_private_key(private_key_pem.encode(), password=None)
            if not isinstance(key, Ed25519PrivateKey):
                raise ValueError("QR key must be an Ed25519 private key")
        else:  # development fallback: ephemeral key (tokens die on restart)
            key = Ed25519PrivateKey.generate()
        self._private = key
        self._public = key.public_key()

    # --- writing ---------------------------------------------------------------
    def sign(self, badge_id: int, version: int, issued_at: datetime) -> str:
        """Compact token for new badges (``issued_at`` stays in the database, not in the QR)."""
        if not (0 <= badge_id < 2**32 and 0 <= version < 2**16):
            raise ValueError("badge id or version out of range for the compact QR")
        payload = _PAYLOAD.pack(badge_id, version)
        signature = self._private.sign(self._context + payload)
        return COMPACT_PREFIX + base64.b32encode(payload + signature).decode().rstrip("=")

    def sign_jwt(self, badge_id: int, version: int, issued_at: datetime) -> str:
        """Original format, kept to test that printed badges remain readable."""
        claims = {"iss": self._issuer, "sub": str(badge_id), "ver": version, "iat": issued_at}
        return jwt.encode(claims, self._private, algorithm="EdDSA")

    # --- reading ---------------------------------------------------------------
    def verify(self, token: str) -> QrClaims:
        token = token.strip()
        if token.startswith(COMPACT_PREFIX):
            return self._verify_compact(token)
        return self._verify_jwt(token)

    def _verify_compact(self, token: str) -> QrClaims:
        if len(token) != _COMPACT_LENGTH:
            raise InvalidTokenError("QR invalide")
        body = token[len(COMPACT_PREFIX):]
        try:
            raw = base64.b32decode(body + "=" * (-len(body) % 8))
            payload, signature = raw[:_PAYLOAD.size], raw[_PAYLOAD.size:]
            self._public.verify(signature, self._context + payload)
        except (binascii.Error, ValueError, InvalidSignature) as exc:
            raise InvalidTokenError("QR invalide") from exc
        badge_id, version = _PAYLOAD.unpack(payload)
        return QrClaims(badge_id=badge_id, version=version)

    def _verify_jwt(self, token: str) -> QrClaims:
        try:
            payload = jwt.decode(
                token,
                self._public,
                algorithms=["EdDSA"],
                issuer=self._issuer,
                options={"require": ["sub", "ver", "iss"]},
            )
            return QrClaims(badge_id=int(payload["sub"]), version=int(payload["ver"]))
        except (jwt.PyJWTError, ValueError) as exc:
            raise InvalidTokenError("QR invalide") from exc


def load_or_create_dev_key(path: str) -> str:
    """Development helper: keep one Ed25519 key in a local file so QR badges survive restarts.

    Production must set BHH_QR_PRIVATE_KEY_PEM instead (and never commit the key).
    """
    key_file = Path(path)
    if key_file.exists():
        return key_file.read_text()
    pem = Ed25519PrivateKey.generate().private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    key_file.write_text(pem)
    return pem
