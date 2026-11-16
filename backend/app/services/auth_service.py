from app.core.clock import Clock
from app.core.exceptions import AuthenticationError, DomainError
from app.core.security import SessionTokenCodec, check_password_policy, hash_password, verify_password
from app.models import User
from app.repositories.repositories import UserRepository
from app.services.audit_service import AuditService


class AuthService:
    def __init__(self, users: UserRepository, codec: SessionTokenCodec, audit: AuditService, clock: Clock) -> None:
        self._users = users
        self._codec = codec
        self._audit = audit
        self._clock = clock

    def login(self, username: str, password: str) -> str:
        user = self._users.by_username(username)
        # Same message for unknown user and bad password: no account enumeration.
        if user is None or not user.is_active or not verify_password(password, user.password_hash):
            raise AuthenticationError("Identifiants invalides")
        return self._codec.issue(user.id)

    def authenticate(self, token: str) -> User:
        user_id, issued_at = self._codec.read(token)
        user = self._users.get(user_id)
        if user is None or not user.is_active:
            raise AuthenticationError("Compte inactif ou introuvable")
        # A password change closes every session opened before it (whole seconds: JWT iat).
        if user.password_changed_at is not None and issued_at.timestamp() < int(user.password_changed_at.timestamp()):
            raise AuthenticationError("Mot de passe modifié : reconnectez-vous")
        return user

    def change_password(self, user: User, current: str, new: str) -> str:
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
        self._audit.record(user.id, "user.password.change", user.username)
        return self._codec.issue(user.id)
