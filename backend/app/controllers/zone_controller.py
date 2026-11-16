from fastapi import APIRouter, Depends, Response, status

from app.controllers.deps import get_zone_service, require
from app.domain.permissions import Permission
from app.models import User
from app.schemas.dto import (
    AccessIn,
    AccessUnitOut,
    AccessZoneOut,
    AuthorizationIn,
    AuthorizationOut,
    CheckpointIn,
    CheckpointOut,
    CheckpointUpdateIn,
    RestrictionsIn,
    UnitIn,
    UnitOut,
    ZoneIn,
    ZoneModeIn,
    ZoneOut,
    ZoneUnitIn,
    ZoneUpdateIn,
)
from app.services.zone_service import ZoneService

router = APIRouter(tags=["zones"])


@router.post("/zones", response_model=ZoneOut, status_code=status.HTTP_201_CREATED)
def create_zone(body: ZoneIn, actor: User = Depends(require(Permission.ZONES_MANAGE)),
                service: ZoneService = Depends(get_zone_service)):
    return service.create_zone(actor.id, body.name, body.antipassback_mode, body.unit_id, code=body.code,
                               description=body.description, sensitivity=body.sensitivity,
                               warn_agent=body.antipassback_warn_agent)


def _changes(body, nullable: tuple[str, ...] = ()) -> dict:
    """Fields actually sent; ``None`` only kept where it means "clear" (code, description)."""
    return {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None or k in nullable}


@router.patch("/zones/{zone_id}", response_model=ZoneOut)
def update_zone(zone_id: int, body: ZoneUpdateIn, actor: User = Depends(require(Permission.ZONES_MANAGE)),
                service: ZoneService = Depends(get_zone_service)):
    return service.update_zone(actor.id, zone_id, _changes(body, ("code", "description")))


@router.delete("/zones/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_zone(zone_id: int, actor: User = Depends(require(Permission.ZONES_MANAGE)),
                service: ZoneService = Depends(get_zone_service)):
    service.delete_zone(actor.id, zone_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/checkpoints/{checkpoint_id}", response_model=CheckpointOut)
def update_checkpoint(checkpoint_id: int, body: CheckpointUpdateIn,
                      actor: User = Depends(require(Permission.ZONES_MANAGE)),
                      service: ZoneService = Depends(get_zone_service)):
    return service.update_checkpoint(actor.id, checkpoint_id, _changes(body))


@router.delete("/checkpoints/{checkpoint_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_checkpoint(checkpoint_id: int, actor: User = Depends(require(Permission.ZONES_MANAGE)),
                      service: ZoneService = Depends(get_zone_service)):
    service.delete_checkpoint(actor.id, checkpoint_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/zones", response_model=list[ZoneOut])
def list_zones(_: User = Depends(require(Permission.ZONES_VIEW)),
               service: ZoneService = Depends(get_zone_service)):
    return service.list_zones()


@router.patch("/zones/{zone_id}/antipassback", response_model=ZoneOut)
def set_antipassback(zone_id: int, body: ZoneModeIn,
                     actor: User = Depends(require(Permission.ZONES_ANTIPASSBACK)),
                     service: ZoneService = Depends(get_zone_service)):
    return service.set_mode(actor.id, zone_id, body.antipassback_mode, body.antipassback_warn_agent)


@router.post("/zones/{zone_id}/checkpoints", response_model=CheckpointOut,
             status_code=status.HTTP_201_CREATED)
def add_checkpoint(zone_id: int, body: CheckpointIn,
                   actor: User = Depends(require(Permission.ZONES_MANAGE)),
                   service: ZoneService = Depends(get_zone_service)):
    return service.add_checkpoint(actor.id, zone_id, body.name, body.direction)


@router.get("/checkpoints", response_model=list[CheckpointOut])
def list_checkpoints(_: User = Depends(require(Permission.ZONES_VIEW)),
                     service: ZoneService = Depends(get_zone_service)):
    return service.list_checkpoints()


@router.put("/authorizations", response_model=AuthorizationOut)
def grant_authorization(body: AuthorizationIn,
                        actor: User = Depends(require(Permission.AUTHORIZATIONS_MANAGE)),
                        service: ZoneService = Depends(get_zone_service)):
    return service.grant(actor.id, body.employee_id, body.zone_id, body.valid_until)


@router.delete("/authorizations/{employee_id}/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_authorization(employee_id: int, zone_id: int,
                         actor: User = Depends(require(Permission.AUTHORIZATIONS_MANAGE)),
                         service: ZoneService = Depends(get_zone_service)):
    service.revoke_authorization(actor.id, employee_id, zone_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/units", response_model=list[UnitOut])
def list_units(_: User = Depends(require(Permission.ZONES_VIEW)),
               service: ZoneService = Depends(get_zone_service)):
    return service.list_units()


@router.post("/units", response_model=UnitOut, status_code=status.HTTP_201_CREATED)
def create_unit(body: UnitIn, actor: User = Depends(require(Permission.ZONES_MANAGE)),
                service: ZoneService = Depends(get_zone_service)):
    return service.create_unit(actor.id, body.name)


@router.patch("/units/{unit_id}", response_model=UnitOut)
def rename_unit(unit_id: int, body: UnitIn, actor: User = Depends(require(Permission.ZONES_MANAGE)),
                service: ZoneService = Depends(get_zone_service)):
    return service.rename_unit(actor.id, unit_id, body.name)


@router.delete("/units/{unit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_unit(unit_id: int, actor: User = Depends(require(Permission.ZONES_MANAGE)),
                service: ZoneService = Depends(get_zone_service)):
    service.delete_unit(actor.id, unit_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/zones/{zone_id}/unit", response_model=ZoneOut)
def move_zone(zone_id: int, body: ZoneUnitIn, actor: User = Depends(require(Permission.ZONES_MANAGE)),
              service: ZoneService = Depends(get_zone_service)):
    return service.move_zone(actor.id, zone_id, body.unit_id)


@router.get("/employees/{employee_id}/access", response_model=list[AccessUnitOut])
def employee_access(employee_id: int, _: User = Depends(require(Permission.EMPLOYEES_VIEW)),
                    service: ZoneService = Depends(get_zone_service)):
    return service.employee_access(employee_id)


@router.put("/employees/{employee_id}/access/{zone_id}/restrictions", response_model=AccessZoneOut)
def set_restrictions(employee_id: int, zone_id: int, body: RestrictionsIn,
                     actor: User = Depends(require(Permission.AUTHORIZATIONS_MANAGE)),
                     service: ZoneService = Depends(get_zone_service)):
    """Temporary access (dates) and weekly time slots of one ticked zone; empty = permanent."""
    return service.set_restrictions(actor.id, employee_id, zone_id, body.valid_from, body.valid_until,
                                    [(s.weekdays, s.start, s.end) for s in body.schedules])


@router.put("/employees/{employee_id}/access", response_model=list[AccessUnitOut])
def set_employee_access(employee_id: int, body: AccessIn,
                        actor: User = Depends(require(Permission.AUTHORIZATIONS_MANAGE)),
                        service: ZoneService = Depends(get_zone_service)):
    return service.set_employee_access(actor.id, employee_id, body.zone_ids)
