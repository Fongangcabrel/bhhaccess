"""Phones: pairing + scanning without login (X-Device-Token), and their back-office management."""
from fastapi import APIRouter, Depends, Header, Query, Request, Response, status

from app.controllers.deps import (
    get_device_service,
    get_photo_signer,
    get_scan_service,
    get_zone_service,
    require,
)
from app.controllers.scan_controller import to_out
from app.core.i18n import request_lang
from app.domain.permissions import Permission
from app.models import Device, User
from app.schemas.dto import (
    CheckpointOut,
    DeviceCodeOut,
    DeviceIn,
    DeviceOut,
    DevicePostIn,
    DevicePostOut,
    DeviceScanOut,
    DeviceScopeIn,
    DeviceSettingsOut,
    DeviceVoiceIn,
    PairIn,
    PairOut,
    ScanManualIn,
    ScanOut,
    ScanQrIn,
)
from app.services.device_service import DeviceService
from app.services.photo_service import PhotoUrlSigner
from app.services.scan_service import ScanService, ScanSource
from app.services.zone_service import ZoneService

router = APIRouter(tags=["devices"])


def current_device(x_device_token: str | None = Header(default=None),
                   service: DeviceService = Depends(get_device_service)) -> Device:
    return service.authenticate(x_device_token)


# --- phone side (no login) ------------------------------------------------------
@router.post("/device/pair", response_model=PairOut)
def pair(body: PairIn, request: Request, service: DeviceService = Depends(get_device_service)):
    client_key = request.client.host if request.client else "unknown"
    device, token = service.pair(body.code, client_key)
    return PairOut(device_token=token, device_name=device.name)


@router.get("/device/settings", response_model=DeviceSettingsOut)
def device_settings(device: Device = Depends(current_device)):
    return DeviceSettingsOut(name=device.name, voice_enabled=device.voice_enabled)


@router.get("/device/checkpoints", response_model=list[CheckpointOut])
def device_checkpoints(device: Device = Depends(current_device), zones: ZoneService = Depends(get_zone_service),
                       devices: DeviceService = Depends(get_device_service)):
    """Only the posts of the phone's perimeter; deactivated posts disappear too."""
    return devices.allowed_checkpoints(device, zones.list_checkpoints(usable_only=True))


@router.post("/device/post", response_model=DevicePostOut)
def device_take_post(body: DevicePostIn, device: Device = Depends(current_device),
                     devices: DeviceService = Depends(get_device_service)):
    """The agent chose a post on the phone (FR-33): a change is written in the audit."""
    devices.take_post(device, body.checkpoint_id)
    return DevicePostOut(checkpoint_id=device.checkpoint.id, current_post=device.current_post,
                         since=device.checkpoint_since)


@router.get("/device/scans", response_model=list[DeviceScanOut])
def device_recent_scans(limit: int = Query(30, ge=1, le=50), device: Device = Depends(current_device),
                        devices: DeviceService = Depends(get_device_service)):
    """This phone's last scans (FR-68), read only."""
    return devices.recent_scans(device, limit)


@router.post("/device/scan", response_model=ScanOut)
def device_scan(body: ScanQrIn, device: Device = Depends(current_device),
                service: ScanService = Depends(get_scan_service), signer: PhotoUrlSigner = Depends(get_photo_signer),
                lang: str = Depends(request_lang),
                devices: DeviceService = Depends(get_device_service)):
    devices.take_post(device, body.checkpoint_id)  # a scan elsewhere is a change of post too
    return to_out(service.scan_qr(ScanSource(device_id=device.id), body.checkpoint_id, body.token), signer, lang)


@router.post("/device/scan/manual", response_model=ScanOut)
def device_scan_manual(body: ScanManualIn, device: Device = Depends(current_device),
                       service: ScanService = Depends(get_scan_service),
                       signer: PhotoUrlSigner = Depends(get_photo_signer),
                lang: str = Depends(request_lang),
                       devices: DeviceService = Depends(get_device_service)):
    devices.take_post(device, body.checkpoint_id)
    result = service.scan_manual(ScanSource(device_id=device.id), body.checkpoint_id, body.matricule)
    return to_out(result, signer, lang)


# --- back-office ---------------------------------------------------------------
@router.get("/devices", response_model=list[DeviceOut])
def list_devices(_: User = Depends(require(Permission.ZONES_VIEW)),
                 service: DeviceService = Depends(get_device_service)):
    return service.all()


@router.post("/devices", response_model=DeviceCodeOut, status_code=status.HTTP_201_CREATED)
def create_device(body: DeviceIn, actor: User = Depends(require(Permission.ZONES_MANAGE)),
                  service: DeviceService = Depends(get_device_service)):
    device, code = service.create(actor.id, body.name)
    return DeviceCodeOut(device=DeviceOut.model_validate(device), code=code)


@router.post("/devices/{device_id}/code", response_model=DeviceCodeOut)
def new_code(device_id: int, actor: User = Depends(require(Permission.ZONES_MANAGE)),
             service: DeviceService = Depends(get_device_service)):
    device, code = service.new_code(actor.id, device_id)
    return DeviceCodeOut(device=DeviceOut.model_validate(device), code=code)


@router.patch("/devices/{device_id}", response_model=DeviceOut)
def rename_device(device_id: int, body: DeviceIn, actor: User = Depends(require(Permission.ZONES_MANAGE)),
                  service: DeviceService = Depends(get_device_service)):
    return service.rename(actor.id, device_id, body.name)


@router.put("/devices/{device_id}/voice", response_model=DeviceOut)
def set_voice(device_id: int, body: DeviceVoiceIn, actor: User = Depends(require(Permission.ZONES_MANAGE)),
              service: DeviceService = Depends(get_device_service)):
    return service.set_voice(actor.id, device_id, body.enabled)


@router.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_device(device_id: int, actor: User = Depends(require(Permission.ZONES_MANAGE)),
                  service: DeviceService = Depends(get_device_service)):
    service.delete(actor.id, device_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/devices/{device_id}/scope", response_model=DeviceOut)
def set_scope(device_id: int, body: DeviceScopeIn, actor: User = Depends(require(Permission.ZONES_MANAGE)),
              service: DeviceService = Depends(get_device_service)):
    """Units / zones / posts the phone covers; it lists and scans only those."""
    return service.set_scope(actor.id, device_id, body.unit_ids, body.zone_ids, body.checkpoint_ids)


@router.post("/devices/{device_id}/revoke", response_model=DeviceOut)
def revoke_device(device_id: int, actor: User = Depends(require(Permission.ZONES_MANAGE)),
                  service: DeviceService = Depends(get_device_service)):
    return service.revoke(actor.id, device_id)
