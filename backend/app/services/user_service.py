"""Accounts, roles and per-person rights, with guardrails.

Guardrails: nobody edits their own rights, the last super admin cannot be removed, and
nobody can hand out a right they do not hold themselves (no privilege escalation).
"""
import re
import unicodedata

from app.core.clock import Clock
from app.core.exceptions import ConflictError, DomainError, ForbiddenError, NotFoundError
from app.core.security import check_password_policy, hash_password
from app.domain.enums import OverrideEffect
from app.domain.permissions import DEFAULT_ROLES, Permission
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
        self._forbid_above(actor, user)
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
        self._forbid_above(actor, user)
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
        self._forbid_above(actor, user)
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
        self._forbid_above(actor, user)
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
        self._forbid_above(actor, user)
        was = next((o.effect.value for o in user.overrides if o.permission == permission.value), None)
        user.overrides[:] = [o for o in user.overrides if o.permission != permission.value]
        self._audit.record(actor.id, "user.override.clear", user.username, permission=permission.value,
                           before={"effect": was}, after={"effect": None})
        return user

    # --- roles -----------------------------------------------------------
    def list_roles(self) -> list[Role]:
        """Templates first (in their usual order), then the custom roles; each with its number of accounts."""
        holders = self._users.count_by_role()
        order = list(DEFAULT_ROLES)
        roles = sorted(self._roles.list(limit=500),
                       key=lambda r: (order.index(r.name) if r.name in order else len(order), r.label.casefold()))
        for role in roles:
            role.users = holders.get(role.id, 0)
            role.is_template = role.name in DEFAULT_ROLES
        return roles

    def create_role(self, actor: User, label: str, permissions: set[Permission]) -> Role:
        """A custom role (FR-07): named freely, with the rights of one's choice among one's own."""
        label = self._free_label(label)
        if not permissions <= PermissionService.effective(actor):
            raise ForbiddenError("Vous ne pouvez pas accorder un droit que vous n'avez pas")
        role = self._roles.add(Role(name=self._unique_name(label), label=label,
                                    permissions=sorted(p.value for p in permissions)))
        self._audit.record(actor.id, "role.create", role.label, after={"permissions": list(role.permissions)})
        role.users, role.is_template = 0, False
        return role

    def rename_role(self, actor: User, role_id: int, label: str) -> Role:
        role = self._require_custom(role_id)
        label = self._free_label(label, role.id)
        before, role.label = role.label, label
        if before != label:
            self._audit.record(actor.id, "role.rename", role.label, before={"label": before}, after={"label": label})
        role.users, role.is_template = self._users.count_by_role().get(role.id, 0), False
        return role

    def delete_role(self, actor: User, role_id: int) -> None:
        """Only an unused custom role: the four templates stay, and nobody is left without a role."""
        role = self._require_custom(role_id)
        if self._users.count_by_role().get(role.id, 0):
            raise ConflictError("Ce rôle est attribué à des comptes : donnez-leur d'abord un autre rôle")
        self._audit.record(actor.id, "role.delete", role.label, before={"permissions": list(role.permissions)})
        self._roles.remove(role)

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

    @staticmethod
    def _forbid_above(actor: User, target: User) -> None:
        """A super admin account is only handled by a super admin (deactivate, role, password, rights)."""
        if target.role.name == SUPER_ADMIN and actor.role.name != SUPER_ADMIN:
            raise ForbiddenError("Seul un super admin peut modifier le compte d'un super admin")

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

    def _require_custom(self, role_id: int) -> Role:
        role = self._require_role(role_id)
        if role.name in DEFAULT_ROLES:
            raise DomainError("Les quatre rôles modèles ne peuvent être ni renommés ni supprimés")
        return role

    def _free_label(self, label: str, own_id: int | None = None) -> str:
        label = " ".join(label.split())
        if not label:
            raise DomainError("Nom du rôle obligatoire")
        if any(r.label.casefold() == label.casefold() and r.id != own_id for r in self._roles.list(limit=500)):
            raise ConflictError("Un rôle porte déjà ce nom")
        return label

    def _unique_name(self, label: str) -> str:
        """Technical name from the label: « Chef d'équipe » -> chef_d_equipe (suffixed if taken)."""
        ascii_ = unicodedata.normalize("NFKD", label).encode("ascii", "ignore").decode()
        base = re.sub(r"[^a-z0-9]+", "_", ascii_.lower()).strip("_")[:50] or "role"
        name, n = base, 2
        while self._roles.by_name(name) is not None:
            name, n = f"{base}_{n}", n + 1
        return name

    def _require_role(self, role_id: int) -> Role:
        role = self._roles.get(role_id)
        if role is None:
            raise NotFoundError("Rôle introuvable")
        return role
