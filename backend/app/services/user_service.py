"""Accounts, roles and per-person rights, with guardrails.

Guardrails: nobody edits their own rights, the last super admin cannot be removed, and
nobody can hand out a right they do not hold themselves (no privilege escalation).
"""
from app.core.clock import Clock
from app.core.exceptions import ConflictError, DomainError, ForbiddenError, NotFoundError
from app.core.security import check_password_policy, hash_password
from app.domain.enums import OverrideEffect
from app.domain.permissions import Permission
from app.models import Role, User, UserPermissionOverride
from app.repositories.repositories import RoleRepository, UserRepository
from app.services.audit_service import AuditService
from app.services.permission_service import PermissionService

SUPER_ADMIN = "super_admin"


class UserService:
    def __init__(self, users: UserRepository, roles: RoleRepository, audit: AuditService, clock: Clock) -> None:
        self._clock = clock
        self._users = users
        self._roles = roles
        self._audit = audit

    # --- accounts --------------------------------------------------------
    def create_user(self, actor: User, *, username: str, full_name: str, password: str, role_id: int) -> User:
        if self._users.by_username(username):
            raise ConflictError(f"Identifiant déjà utilisé : {username}")
        role = self._require_role(role_id)
        self._guard_role_grant(actor, role)
        check_password_policy(password, username)
        # The admin chose this password: the person must replace it at first login.
        user = self._users.add(
            User(username=username, full_name=full_name, password_hash=hash_password(password), role_id=role.id,
                 must_change_password=True)
        )
        self._audit.record(actor.id, "user.create", username, role=role.name)
        return user

    def list_users(self) -> list[User]:
        return self._users.list(limit=500)

    def set_active(self, actor: User, user_id: int, active: bool) -> User:
        user = self._require_user(user_id)
        self._forbid_self(actor, user)
        if not active:
            self._forbid_last_super_admin(user)
        was, user.is_active = user.is_active, active
        self._audit.record(actor.id, "user.activate" if active else "user.deactivate", user.username,
                           before={"active": was}, after={"active": active})
        return user

    def assign_role(self, actor: User, user_id: int, role_id: int) -> User:
        user = self._require_user(user_id)
        role = self._require_role(role_id)
        self._forbid_self(actor, user)
        self._guard_role_grant(actor, role)
        if role.name != SUPER_ADMIN:
            self._forbid_last_super_admin(user)
        old, user.role_id, user.role = user.role.name, role.id, role
        self._audit.record(actor.id, "user.role", user.username, before={"role": old}, after={"role": role.name})
        return user

    def reset_password(self, actor: User, user_id: int, new_password: str) -> User:
        """Temporary password set by an admin: the person must change it at next login."""
        user = self._require_user(user_id)
        if actor.id == user.id:
            raise ForbiddenError("Utilisez « Changer mon mot de passe » pour votre propre compte")
        check_password_policy(new_password, user.username)
        user.password_hash = hash_password(new_password)
        user.must_change_password = True
        user.password_changed_at = self._clock.now()  # closes the sessions already open
        self._users.flush()
        self._audit.record(actor.id, "user.password.reset", user.username)
        return user

    # --- per-person exceptions ------------------------------------------
    def set_override(self, actor: User, user_id: int, permission: Permission, effect: OverrideEffect) -> User:
        user = self._require_user(user_id)
        self._forbid_self(actor, user)
        if effect == OverrideEffect.ALLOW and permission not in PermissionService.effective(actor):
            raise ForbiddenError("Vous ne pouvez pas accorder un droit que vous n'avez pas")
        existing = next((o for o in user.overrides if o.permission == permission.value), None)
        was = existing.effect.value if existing else None
        if existing:
            existing.effect = effect
        else:
            user.overrides.append(UserPermissionOverride(permission=permission.value, effect=effect))
        self._audit.record(actor.id, "user.override", user.username, permission=permission.value,
                           before={"effect": was}, after={"effect": effect.value})
        return user

    def clear_override(self, actor: User, user_id: int, permission: Permission) -> User:
        user = self._require_user(user_id)
        self._forbid_self(actor, user)
        was = next((o.effect.value for o in user.overrides if o.permission == permission.value), None)
        user.overrides[:] = [o for o in user.overrides if o.permission != permission.value]
        self._audit.record(actor.id, "user.override.clear", user.username, permission=permission.value,
                           before={"effect": was}, after={"effect": None})
        return user

    # --- roles -----------------------------------------------------------
    def list_roles(self) -> list[Role]:
        return self._roles.list()

    def update_role(self, actor: User, role_id: int, permissions: set[Permission]) -> Role:
        """Changing a bundle applies at once to everyone holding the role (rights are read live)."""
        role = self._require_role(role_id)
        if role.name == SUPER_ADMIN:
            raise DomainError("Le rôle super admin ne peut pas être modifié")
        if not permissions <= PermissionService.effective(actor):
            raise ForbiddenError("Vous ne pouvez pas accorder un droit que vous n'avez pas")
        old = set(role.permissions)
        role.permissions = sorted(p.value for p in permissions)
        self._audit.record(actor.id, "role.update", role.name,
                           added=sorted({p.value for p in permissions} - old),
                           removed=sorted(old - {p.value for p in permissions}),
                           before={"permissions": sorted(old)}, after={"permissions": list(role.permissions)})
        return role

    # --- guardrails ------------------------------------------------------
    @staticmethod
    def _forbid_self(actor: User, target: User) -> None:
        if actor.id == target.id:
            raise ForbiddenError("Vous ne pouvez pas modifier vos propres droits")

    def _forbid_last_super_admin(self, target: User) -> None:
        if target.role.name != SUPER_ADMIN:
            return
        remaining = [u for u in self._users.list(limit=1000)
                     if u.role.name == SUPER_ADMIN and u.is_active and u.id != target.id]
        if not remaining:
            raise ConflictError("Impossible : c'est le dernier super admin actif")

    @staticmethod
    def _guard_role_grant(actor: User, role: Role) -> None:
        if not {Permission(p) for p in role.permissions} <= PermissionService.effective(actor):
            raise ForbiddenError("Ce rôle contient des droits que vous n'avez pas")

    def _require_user(self, user_id: int) -> User:
        user = self._users.get(user_id)
        if user is None:
            raise NotFoundError("Utilisateur introuvable")
        return user

    def _require_role(self, role_id: int) -> Role:
        role = self._roles.get(role_id)
        if role is None:
            raise NotFoundError("Rôle introuvable")
        return role
