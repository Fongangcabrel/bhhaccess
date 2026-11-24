from fastapi import APIRouter, Depends, Response, status

from app.controllers.deps import get_auth_service, get_current_user
from app.models import User
from app.schemas.dto import LoginIn, MeOut, PasswordChangeIn, RefreshIn, TokenOut
from app.services.auth_service import AuthService, SessionTokens
from app.services.permission_service import PermissionService

router = APIRouter(prefix="/auth", tags=["auth"])


def _out(tokens: SessionTokens) -> TokenOut:
    return TokenOut(access_token=tokens.access_token, refresh_token=tokens.refresh_token,
                    expires_in=tokens.expires_in)


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, service: AuthService = Depends(get_auth_service)) -> TokenOut:
    return _out(service.login(body.username, body.password))


@router.post("/refresh", response_model=TokenOut)
def refresh(body: RefreshIn, service: AuthService = Depends(get_auth_service)) -> TokenOut:
    """New access token + next refresh token; the one sent is used up."""
    return _out(service.refresh(body.refresh_token))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(body: RefreshIn, service: AuthService = Depends(get_auth_service)) -> Response:
    service.logout(body.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(get_current_user)) -> MeOut:
    perms = sorted(p.value for p in PermissionService.effective(user))
    return MeOut(id=user.id, username=user.username, full_name=user.full_name,
                 role=user.role.name, permissions=perms, must_change_password=user.must_change_password)


@router.post("/password", response_model=TokenOut)
def change_password(body: PasswordChangeIn, user: User = Depends(get_current_user),
                    service: AuthService = Depends(get_auth_service)) -> TokenOut:
    """Change one's own password. Returns a new session; the other sessions are closed."""
    return _out(service.change_password(user, body.current_password, body.new_password))
