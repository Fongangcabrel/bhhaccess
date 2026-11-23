from fastapi import APIRouter, Depends, Response, status

from app.controllers.deps import get_user_service, require
from app.domain.permissions import PERMISSION_CATALOGUE, Permission
from app.models import User
from app.schemas.dto import (
    ActiveIn,
    CatalogueGroupOut,
    OverrideIn,
    PasswordResetIn,
    RoleAssignIn,
    RoleCreateIn,
    RoleOut,
    RoleRenameIn,
    RoleUpdateIn,
    UserIn,
    UserOut,
)
from app.services.user_service import UserService

router = APIRouter(tags=["users"])


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(body: UserIn, actor: User = Depends(require(Permission.USERS_MANAGE)),
                service: UserService = Depends(get_user_service)):
    return service.create_user(actor, **body.model_dump())


@router.get("/users", response_model=list[UserOut])
def list_users(_: User = Depends(require(Permission.USERS_MANAGE)),
               service: UserService = Depends(get_user_service)):
    return service.list_users()


@router.patch("/users/{user_id}/active", response_model=UserOut)
def set_active(user_id: int, body: ActiveIn, actor: User = Depends(require(Permission.USERS_MANAGE)),
               service: UserService = Depends(get_user_service)):
    return service.set_active(actor, user_id, body.is_active)


@router.post("/users/{user_id}/password", response_model=UserOut)
def reset_password(user_id: int, body: PasswordResetIn, actor: User = Depends(require(Permission.USERS_MANAGE)),
                   service: UserService = Depends(get_user_service)):
    """Temporary password: the person must change it at next login; their open sessions stop."""
    return service.reset_password(actor, user_id, body.new_password)


@router.put("/users/{user_id}/role", response_model=UserOut)
def assign_role(user_id: int, body: RoleAssignIn, actor: User = Depends(require(Permission.ROLES_ASSIGN)),
                service: UserService = Depends(get_user_service)):
    return service.assign_role(actor, user_id, body.role_id)


@router.put("/users/{user_id}/overrides", response_model=UserOut)
def set_override(user_id: int, body: OverrideIn, actor: User = Depends(require(Permission.ROLES_ASSIGN)),
                 service: UserService = Depends(get_user_service)):
    return service.set_override(actor, user_id, body.permission, body.effect)


@router.delete("/users/{user_id}/overrides/{permission}", response_model=UserOut)
def clear_override(user_id: int, permission: Permission,
                   actor: User = Depends(require(Permission.ROLES_ASSIGN)),
                   service: UserService = Depends(get_user_service)):
    return service.clear_override(actor, user_id, permission)


@router.get("/roles", response_model=list[RoleOut])
def list_roles(_: User = Depends(require(Permission.ROLES_ASSIGN)),
               service: UserService = Depends(get_user_service)):
    return service.list_roles()


@router.put("/roles/{role_id}", response_model=RoleOut)
def update_role(role_id: int, body: RoleUpdateIn, actor: User = Depends(require(Permission.ROLES_MANAGE)),
                service: UserService = Depends(get_user_service)):
    role = service.update_role(actor, role_id, set(body.permissions))
    return next(r for r in service.list_roles() if r.id == role.id)


@router.get("/permissions", response_model=list[CatalogueGroupOut])
def permission_catalogue(_: User = Depends(require(Permission.ROLES_ASSIGN))):
    """The catalogue of actions, grouped by theme (FR-05)."""
    return [CatalogueGroupOut(theme=theme, permissions=[{"code": p.value, "label": label} for p, label in items])
            for theme, items in PERMISSION_CATALOGUE]


@router.post("/roles", response_model=RoleOut, status_code=status.HTTP_201_CREATED)
def create_role(body: RoleCreateIn, actor: User = Depends(require(Permission.ROLES_MANAGE)),
                service: UserService = Depends(get_user_service)):
    return service.create_role(actor, body.label, set(body.permissions))


@router.patch("/roles/{role_id}", response_model=RoleOut)
def rename_role(role_id: int, body: RoleRenameIn, actor: User = Depends(require(Permission.ROLES_MANAGE)),
                service: UserService = Depends(get_user_service)):
    return service.rename_role(actor, role_id, body.label)


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(role_id: int, actor: User = Depends(require(Permission.ROLES_MANAGE)),
                service: UserService = Depends(get_user_service)):
    service.delete_role(actor, role_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
