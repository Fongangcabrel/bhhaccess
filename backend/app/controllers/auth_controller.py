from fastapi import APIRouter, Depends

from app.controllers.deps import get_auth_service, get_current_user
from app.models import User
from app.schemas.dto import LoginIn, MeOut, PasswordChangeIn, TokenOut
from app.services.auth_service import AuthService
from app.services.permission_service import PermissionService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, service: AuthService = Depends(get_auth_service)) -> TokenOut:
    return TokenOut(access_token=service.login(body.username, body.password))


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(get_current_user)) -> MeOut:
    perms = sorted(p.value for p in PermissionService.effective(user))
    return MeOut(id=user.id, username=user.username, full_name=user.full_name,
                 role=user.role.name, permissions=perms, must_change_password=user.must_change_password)


@router.post("/password", response_model=TokenOut)
def change_password(body: PasswordChangeIn, user: User = Depends(get_current_user),
                    service: AuthService = Depends(get_auth_service)) -> TokenOut:
    """Change one's own password. Returns a new session; the other sessions are closed."""
    return TokenOut(access_token=service.change_password(user, body.current_password, body.new_password))
