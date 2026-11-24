"""Password hashing and API session tokens (distinct from badge QR tokens)."""
import re
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.clock import Clock
from app.core.exceptions import AuthenticationError, DomainError

_hasher = PasswordHasher()


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def check_password_policy(password: str, username: str) -> None:
    """Minimum rules for a back-office password; the message tells the user what to fix."""
    if len(password) < 8:
        raise DomainError("Mot de passe trop court : 8 caractères minimum")
    if len(password) > 128:
        raise DomainError("Mot de passe trop long : 128 caractères maximum")
    if not re.search(r"[A-Za-zÀ-ÿ]", password) or not re.search(r"\d", password):
        raise DomainError("Le mot de passe doit contenir au moins une lettre et un chiffre")
    if password.casefold() == username.casefold():
        raise DomainError("Le mot de passe ne doit pas être l'identifiant")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, plain)
    except VerifyMismatchError:
        return False


class SessionTokenCodec:
    """Issues and reads short-lived bearer tokens for operators (HS256)."""

    def __init__(self, secret: str, ttl_minutes: int, clock: Clock) -> None:
        self._secret = secret
        self._ttl = timedelta(minutes=ttl_minutes)
        self._clock = clock

    def issue(self, user_id: int, ttl_minutes: int | None = None) -> str:
        """``ttl_minutes``: the duration set in the console (session.access_minutes), else the default."""
        now = self._clock.now()
        ttl = timedelta(minutes=ttl_minutes) if ttl_minutes is not None else self._ttl
        payload = {"sub": str(user_id), "iat": now, "exp": now + ttl}
        return jwt.encode(payload, self._secret, algorithm="HS256")

    def read(self, token: str) -> tuple[int, datetime]:
        """User id and issue time of a valid session token."""
        try:
            # Expiry is checked against the injected clock, not the OS clock.
            payload = jwt.decode(token, self._secret, algorithms=["HS256"],
                                 options={"verify_exp": False, "verify_iat": False})
            if payload["exp"] <= self._clock.now().timestamp():
                raise AuthenticationError("Session invalide ou expirée")
            return int(payload["sub"]), datetime.fromtimestamp(int(payload["iat"]), UTC)
        except (jwt.PyJWTError, KeyError, ValueError, TypeError) as exc:
            raise AuthenticationError("Session invalide ou expirée") from exc

    def read_user_id(self, token: str) -> int:
        return self.read(token)[0]
