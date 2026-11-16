from fastapi import APIRouter, Depends, Response, status

from app.controllers.deps import get_badge_service, get_qr_renderer, require
from app.domain.permissions import Permission
from app.models import User
from app.schemas.dto import BadgeIssueIn, BadgeOut, BadgeRevokeIn, QrTokenOut
from app.services.badge_service import BadgeService
from app.services.qr_image import QrImageRenderer

router = APIRouter(prefix="/badges", tags=["badges"])


@router.post("", response_model=BadgeOut, status_code=status.HTTP_201_CREATED)
def issue_badge(body: BadgeIssueIn, actor: User = Depends(require(Permission.BADGES_ISSUE)),
                service: BadgeService = Depends(get_badge_service)):
    return service.issue(actor.id, body.employee_id, body.expires_at)


@router.post("/{badge_id}/revoke", response_model=BadgeOut)
def revoke_badge(badge_id: int, body: BadgeRevokeIn,
                 actor: User = Depends(require(Permission.BADGES_REVOKE)),
                 service: BadgeService = Depends(get_badge_service)):
    """Revoke with a reason: perte, vol, départ or autre (with a note)."""
    return service.revoke(actor.id, badge_id, body.reason, body.note)


@router.get("/{badge_id}/qr-token", response_model=QrTokenOut)
def qr_token(badge_id: int, _: User = Depends(require(Permission.BADGES_ISSUE)),
             service: BadgeService = Depends(get_badge_service)):
    return QrTokenOut(badge_id=badge_id, token=service.qr_token(badge_id))


@router.get("/{badge_id}/qr.png", response_class=Response)
def qr_image(badge_id: int, _: User = Depends(require(Permission.BADGES_ISSUE)),
             service: BadgeService = Depends(get_badge_service),
             renderer: QrImageRenderer = Depends(get_qr_renderer)):
    """Printable QR (ECC H, BHH logo at the centre, matricule underneath)."""
    badge = service.get(badge_id)
    png = renderer.render(service.qr_token(badge_id), service.matricule_of(badge))
    return Response(content=png, media_type="image/png")
