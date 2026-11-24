"""System configuration (system.config): session durations and alert thresholds."""
from fastapi import APIRouter, Depends

from app.controllers.deps import get_settings_service, require
from app.domain.permissions import Permission
from app.models import User
from app.schemas.dto import SettingOut, SettingsIn
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
