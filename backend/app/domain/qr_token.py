"""Badge QR token: signed with Ed25519, permanent, and carrying no personal data.

Three formats are read; new prints get ``B2``.

* ``B2`` + base32: key id (2 bytes) + badge id (4 bytes) + version (2 bytes) + Ed25519
  signature (64 bytes) = 118 characters, all in the QR "alphanumeric" set. With error
  correction H that is a version-8 QR (49 modules) instead of version 15 (77 modules) for the
  JWT: much bigger modules at the same 4 cm print size, so phones read it faster, logo included.
  The key id (signed with the rest) says which key to check: the signing key can be replaced
  while badges printed with the previous one keep working until they are reprinted.
* ``B1``: the same without key id (tâche 9), tried with every accepted key.
* JWT (EdDSA): the original format, still accepted so already printed badges keep working.

Depends on the ``TokenSigner`` abstraction so the algorithm can change without touching callers.
"""
import base64
import binascii
import hashlib
import re
import struct
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

import jwt
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from app.core.exceptions import InvalidTokenError

COMPACT_PREFIX = "B1"  # without key id: still read
KEYED_PREFIX = "B2"  # with key id: written for new prints
_PAYLOAD = struct.Struct(">IH")  # badge id (uint32), version (uint16)
_KEYED_PAYLOAD = struct.Struct(">2sIH")  # key id (2 bytes), badge id, version
_SIGNATURE_SIZE = 64


def _b32_length(size: int) -> int:
    return -(-size * 8 // 5)  # base32 without padding


_COMPACT_LENGTH = len(COMPACT_PREFIX) + _b32_length(_PAYLOAD.size + _SIGNATURE_SIZE)  # 114
_KEYED_LENGTH = len(KEYED_PREFIX) + _b32_length(_KEYED_PAYLOAD.size + _SIGNATURE_SIZE)  # 118
_PEM_BLOCK = re.compile(r"-----BEGIN [A-Z ]+-----.+?-----END [A-Z ]+-----", re.S)


def _raw(public: Ed25519PublicKey) -> bytes:
    return public.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def key_id(public: Ed25519PublicKey) -> str:
    """Short public fingerprint (4 hex characters) carried by the QR and shown in the console."""
    return hashlib.sha256(_raw(public)).digest()[:2].hex().upper()


def _load_key(pem: str) -> Ed25519PublicKey | Ed25519PrivateKey:
    if "PUBLIC KEY" in pem:
        key = serialization.load_pem_public_key(pem.encode())
    else:
        key = serialization.load_pem_private_key(pem.encode(), password=None)
    if not isinstance(key, Ed25519PrivateKey | Ed25519PublicKey):
        raise ValueError("QR key must be an Ed25519 key")
    return key


def previous_public_keys(pems: str) -> list[Ed25519PublicKey]:
    """Former signing keys (private or public PEM blocks, one after the other): verification only."""
    keys = []
    for block in _PEM_BLOCK.findall(pems or ""):
        key = _load_key(block)
        keys.append(key.public_key() if isinstance(key, Ed25519PrivateKey) else key)
    return keys


@dataclass(frozen=True)
class QrClaims:
    badge_id: int
    version: int


class TokenSigner(Protocol):
    key_id: str  # key of new QR codes

    def sign(self, badge_id: int, version: int, issued_at: datetime) -> str: ...
    def verify(self, token: str) -> QrClaims: ...
    def key_ids(self) -> list[str]: ...


class Ed25519TokenSigner:
    def __init__(self, private_key_pem: str, issuer: str, previous_keys_pem: str = "") -> None:
        self._issuer = issuer
        # Domain separation: a compact signature is only valid for this issuer and this format.
        self._context = f"{issuer}|badge-qr|v1|".encode()
        self._keyed_context = f"{issuer}|badge-qr|v2|".encode()
        if private_key_pem:
            key = _load_key(private_key_pem)
            if not isinstance(key, Ed25519PrivateKey):
                raise ValueError("QR key must be an Ed25519 private key")
        else:  # development fallback: ephemeral key (tokens die on restart)
            key = Ed25519PrivateKey.generate()
        self._private = key
        self._public = key.public_key()
        self.key_id = key_id(self._public)
        # Active key first, then the former ones (verification only), without duplicates.
        self._publics: list[Ed25519PublicKey] = [self._public]
        for public in previous_public_keys(previous_keys_pem):
            if _raw(public) not in {_raw(k) for k in self._publics}:
                self._publics.append(public)

    def key_ids(self) -> list[str]:
        """Accepted keys, the active one first."""
        return [key_id(k) for k in self._publics]

    # --- writing ---------------------------------------------------------------
    def sign(self, badge_id: int, version: int, issued_at: datetime) -> str:
        """``B2`` token for new prints (``issued_at`` stays in the database, not in the QR)."""
        self._check_range(badge_id, version)
        payload = _KEYED_PAYLOAD.pack(bytes.fromhex(self.key_id), badge_id, version)
        signature = self._private.sign(self._keyed_context + payload)
        return KEYED_PREFIX + base64.b32encode(payload + signature).decode().rstrip("=")

    def sign_compact(self, badge_id: int, version: int, issued_at: datetime) -> str:
        """``B1`` format (no key id), kept to test that printed badges remain readable."""
        self._check_range(badge_id, version)
        payload = _PAYLOAD.pack(badge_id, version)
        signature = self._private.sign(self._context + payload)
        return COMPACT_PREFIX + base64.b32encode(payload + signature).decode().rstrip("=")

    @staticmethod
    def _check_range(badge_id: int, version: int) -> None:
        if not (0 <= badge_id < 2**32 and 0 <= version < 2**16):
            raise ValueError("badge id or version out of range for the compact QR")

    def sign_jwt(self, badge_id: int, version: int, issued_at: datetime) -> str:
        """Original format, kept to test that printed badges remain readable."""
        claims = {"iss": self._issuer, "sub": str(badge_id), "ver": version, "iat": issued_at}
        return jwt.encode(claims, self._private, algorithm="EdDSA")

    # --- reading ---------------------------------------------------------------
    def verify(self, token: str) -> QrClaims:
        token = token.strip()
        if token.startswith(KEYED_PREFIX):
            return self._verify_keyed(token)
        if token.startswith(COMPACT_PREFIX):
            return self._verify_compact(token)
        return self._verify_jwt(token)

    @staticmethod
    def _decode(token: str, prefix: str, length: int) -> bytes:
        if len(token) != length:
            raise InvalidTokenError("QR invalide")
        body = token[len(prefix):]
        try:
            return base64.b32decode(body + "=" * (-len(body) % 8))
        except (binascii.Error, ValueError) as exc:
            raise InvalidTokenError("QR invalide") from exc

    @staticmethod
    def _check(keys: list[Ed25519PublicKey], signature: bytes, message: bytes) -> None:
        for public in keys:
            try:
                public.verify(signature, message)
                return
            except InvalidSignature:
                continue
        raise InvalidTokenError("QR invalide")

    def _verify_keyed(self, token: str) -> QrClaims:
        raw = self._decode(token, KEYED_PREFIX, _KEYED_LENGTH)
        payload, signature = raw[:_KEYED_PAYLOAD.size], raw[_KEYED_PAYLOAD.size:]
        kid, badge_id, version = _KEYED_PAYLOAD.unpack(payload)
        # Only the accepted keys with this id: a key removed from the configuration is refused.
        keys = [k for k in self._publics if key_id(k) == kid.hex().upper()]
        self._check(keys, signature, self._keyed_context + payload)
        return QrClaims(badge_id=badge_id, version=version)

    def _verify_compact(self, token: str) -> QrClaims:
        raw = self._decode(token, COMPACT_PREFIX, _COMPACT_LENGTH)
        payload, signature = raw[:_PAYLOAD.size], raw[_PAYLOAD.size:]
        self._check(self._publics, signature, self._context + payload)
        badge_id, version = _PAYLOAD.unpack(payload)
        return QrClaims(badge_id=badge_id, version=version)

    def _verify_jwt(self, token: str) -> QrClaims:
        for public in self._publics:
            try:
                payload = jwt.decode(
                    token,
                    public,
                    algorithms=["EdDSA"],
                    issuer=self._issuer,
                    options={"require": ["sub", "ver", "iss"]},
                )
                return QrClaims(badge_id=int(payload["sub"]), version=int(payload["ver"]))
            except jwt.InvalidSignatureError:
                continue  # maybe signed by a former key
            except (jwt.PyJWTError, ValueError) as exc:
                raise InvalidTokenError("QR invalide") from exc
        raise InvalidTokenError("QR invalide")


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
