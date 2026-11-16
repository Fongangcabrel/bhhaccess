from app.core.exceptions import ForbiddenError
from app.domain.enums import OverrideEffect
from app.domain.permissions import Permission
from app.models import User


class PermissionService:
    """Effective rights = role bundle + per-user ALLOW overrides - per-user DENY overrides.

    Evaluated server-side on every request, so a change applies immediately.
    """

    @staticmethod
    def effective(user: User) -> set[Permission]:
        granted = {Permission(p) for p in user.role.permissions}
        for override in user.overrides:
            perm = Permission(override.permission)
            if override.effect == OverrideEffect.ALLOW:
                granted.add(perm)
            else:
                granted.discard(perm)
        return granted

    def require(self, user: User, permission: Permission) -> None:
        if permission not in self.effective(user):
            raise ForbiddenError(f"Droit requis : {permission.value}")
