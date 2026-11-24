"""System configuration (system.config): session durations, alert thresholds, QR keys."""
from fastapi import APIRouter, Depends

from app.controllers.deps import get_badge_service, get_settings_service, require
from app.domain.permissions import Permission
from app.models import User
from app.schemas.dto import QrKeysOut, SettingOut, SettingsIn
from app.services.badge_service import BadgeService
from app.services.settings_service import SettingsService

router = APIRouter(tags=["settings"])


@router.get("/settings", response_model=list[SettingOut])
def read_settings(_: User = Depends(require(Permission.SYSTEM_CONFIG)),
                  service: SettingsService = Depends(get_settings_service)):
    return service.describe()


@router.patch("/settings", response_model=list[SettingOut])
def change_settings(body: SettingsIn, actor: User = Depends(require(Permission.SYSTEM_CONFIG)),
                    service: SettingsService = Depends(get_settings_service)):
    return service.update(actor.id, body.values)


@router.get("/qr-keys", response_model=QrKeysOut)
def qr_keys(_: User = Depends(require(Permission.SYSTEM_CONFIG)),
            service: BadgeService = Depends(get_badge_service)):
    """QR signing keys accepted at the scan and the active badges still printed with each one."""
    return service.qr_keys()
