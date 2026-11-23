from fastapi import APIRouter, Depends, status

from app.controllers.deps import get_photo_signer, get_presence_service, get_scan_service, require
from app.core.i18n import request_lang, tr
from app.domain.permissions import Permission
from app.models import User
from app.schemas.dto import ScanManualIn, ScannedEmployee, ScanOut, ScanQrIn, UnblockIn
from app.services.photo_service import PhotoUrlSigner
from app.services.presence_service import PresenceService
from app.services.scan_service import ScanResult, ScanService, ScanSource

router = APIRouter(tags=["scan"])


def to_out(result: ScanResult, signer: PhotoUrlSigner, lang: str = "fr") -> ScanOut:
    """The agent sees the photo to compare it with the face (FR-63); never for REFUSE_INVALIDE."""
    employee = None
    if result.employee is not None:
        employee = ScannedEmployee.model_validate(result.employee).model_copy(
            update={"photo_url": signer.url_for(result.employee)})
    return ScanOut(
        verdict=result.verdict, flags=list(result.flags), occurred_at=result.occurred_at,
        log_id=result.log_id, direction=result.direction, zone=result.zone_name,
        checkpoint=result.checkpoint_name,
        employee=employee, warning=result.warning,
        last_entry_at=result.last_entry_at, last_entry_checkpoint=result.last_entry_checkpoint,
        detail=tr(result.detail, lang), alert=result.alert, repeat=result.repeat,
    )


@router.post("/scan", response_model=ScanOut)
def scan(body: ScanQrIn, agent: User = Depends(require(Permission.SCAN_PERFORM)),
         service: ScanService = Depends(get_scan_service), signer: PhotoUrlSigner = Depends(get_photo_signer),
                lang: str = Depends(request_lang)):
    return to_out(service.scan_qr(ScanSource(operator_id=agent.id), body.checkpoint_id, body.token), signer, lang)


@router.post("/scan/manual", response_model=ScanOut)
def scan_manual(body: ScanManualIn, agent: User = Depends(require(Permission.SCAN_MANUAL)),
                service: ScanService = Depends(get_scan_service), signer: PhotoUrlSigner = Depends(get_photo_signer),
                lang: str = Depends(request_lang)):
    result = service.scan_manual(ScanSource(operator_id=agent.id), body.checkpoint_id, body.matricule)
    return to_out(result, signer, lang)


@router.post("/presence/unblock", status_code=status.HTTP_204_NO_CONTENT)
def unblock(body: UnblockIn, actor: User = Depends(require(Permission.PRESENCE_UNBLOCK)),
            service: PresenceService = Depends(get_presence_service)) -> None:
    service.unblock(actor.id, body.employee_id, body.zone_id, body.mode, body.reason)
