"""Back-office sessions (FR-01): short access token + refresh token renewed without logging in again.

* The access token (JWT, a few minutes) is sent on every call.
* The refresh token is opaque and stored hashed; each use revokes it and gives the next one of the
  same session (rotation). The session ends at a fixed time after the login, whatever the renewals.
* A refresh token used twice was copied: the whole session stops at once (and it is audited).
* A password change or reset, or a deactivated account, also ends the sessions.
"""
import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta

from app.core.clock import Clock
from app.core.exceptions import AuthenticationError, DomainError
from app.core.security import SessionTokenCodec, check_password_policy, hash_password, verify_password
from app.models import User
from app.models.session import RefreshToken
from app.repositories.repositories import RefreshTokenRepository, UserRepository
from app.services.audit_service import AuditService
from app.services.settings_service import SettingsService

INVALID_REFRESH = "Session expirée : reconnectez-vous"


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass(frozen=True)
class SessionTokens:
    access_token: str
    refresh_token: str
    expires_in: int  # seconds of validity of the access token


class AuthService:
    def __init__(self, users: UserRepository, codec: SessionTokenCodec, audit: AuditService, clock: Clock,
                 refresh_tokens: RefreshTokenRepository, settings: SettingsService) -> None:
        self._users = users
        self._codec = codec
        self._audit = audit
        self._clock = clock
        self._refresh = refresh_tokens
        self._settings = settings

    def login(self, username: str, password: str) -> SessionTokens:
        user = self._users.by_username(username)
        # Same message for unknown user and bad password: no account enumeration.
        if user is None or not user.is_active or not verify_password(password, user.password_hash):
            raise AuthenticationError("Identifiants invalides")
        return self._open_session(user)

    def refresh(self, token: str) -> SessionTokens:
        """Next tokens of the session; the refresh token given is used up."""
        now = self._clock.now()
        current = self._refresh.by_hash(_hash(token)) if token else None
        if current is None:
            raise AuthenticationError(INVALID_REFRESH)
        if current.revoked_at is not None:
            # Already used or ended: someone else holds a copy. Stop the whole session, and keep that
            # even though the request fails (the error would otherwise roll it back).
            if self._refresh.revoke_family(current.family, now):
                self._audit.record(current.user_id, "user.session.reused", None)
            self._refresh.commit_now()
            raise AuthenticationError(INVALID_REFRESH)
        user = self._users.get(current.user_id)
        ended_by_password = (user is not None and user.password_changed_at is not None
                             and current.started_at.timestamp() < int(user.password_changed_at.timestamp()))
        if current.expires_at <= now or user is None or not user.is_active or ended_by_password:
            current.revoked_at = now
            raise AuthenticationError(INVALID_REFRESH)
        current.revoked_at = now
        return self._issue(user, current.family, current.started_at, current.expires_at)

    def logout(self, token: str) -> None:
        """Ends the session of this refresh token (the access token dies within minutes)."""
        current = self._refresh.by_hash(_hash(token)) if token else None
        if current is not None:
            self._refresh.revoke_family(current.family, self._clock.now())

    def authenticate(self, token: str) -> User:
        user_id, issued_at = self._codec.read(token)
        user = self._users.get(user_id)
        if user is None or not user.is_active:
            raise AuthenticationError("Compte inactif ou introuvable")
        # A password change closes every session opened before it (whole seconds: JWT iat).
        if user.password_changed_at is not None and issued_at.timestamp() < int(user.password_changed_at.timestamp()):
            raise AuthenticationError("Mot de passe modifié : reconnectez-vous")
        return user

    def change_password(self, user: User, current: str, new: str) -> SessionTokens:
        """The person changes their own password; returns a fresh session (the old ones stop)."""
        if not verify_password(current, user.password_hash):
            raise DomainError("Mot de passe actuel incorrect")
        if verify_password(new, user.password_hash):
            raise DomainError("Choisissez un mot de passe différent de l'actuel")
        check_password_policy(new, user.username)
        user.password_hash = hash_password(new)
        user.must_change_password = False
        user.password_changed_at = self._clock.now()
        self._users.flush()
        self._refresh.revoke_user(user.id, self._clock.now())
        self._audit.record(user.id, "user.password.change", user.username)
        return self._open_session(user)

    # --- internals -----------------------------------------------------------
    def _open_session(self, user: User) -> SessionTokens:
        now = self._clock.now()
        hours = self._settings.get("session.refresh_hours")
        return self._issue(user, secrets.token_hex(16), now, now + timedelta(hours=hours))

    def _issue(self, user: User, family: str, started_at, expires_at) -> SessionTokens:
        minutes = self._settings.get("session.access_minutes")
        refresh = secrets.token_urlsafe(32)
        self._refresh.add(RefreshToken(user_id=user.id, token_hash=_hash(refresh), family=family,
                                       started_at=started_at, created_at=self._clock.now(), expires_at=expires_at))
        return SessionTokens(self._codec.issue(user.id, ttl_minutes=minutes), refresh, minutes * 60)
