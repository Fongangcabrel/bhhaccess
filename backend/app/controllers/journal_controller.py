
from fastapi import APIRouter, Depends, Query, Request
from pydantic import AwareDatetime

from app.controllers.deps import get_audit, get_journal_service, get_session, require
from app.domain.enums import Direction, Flag, ScanMethod, Verdict
from app.domain.permissions import Permission
from app.models import User
from app.schemas.dto import AuditActorOut, AuditOut, LogOut, PurgeIn, PurgeOut
from app.services.audit_service import AuditFilters, AuditService
from app.services.journal_service import JournalService

router = APIRouter(tags=["journal"])


@router.get("/logs", response_model=list[LogOut])
def search_logs(
    employee_id: int | None = None, department_id: int | None = None, entity_id: int | None = None,
    zone_id: int | None = None, unit_id: int | None = None, agent_id: int | None = None,
    checkpoint_id: int | None = None,
    verdict: Verdict | None = None, direction: Direction | None = None,
    date_from: AwareDatetime | None = None, date_to: AwareDatetime | None = None,
    flag: Flag | None = None, method: ScanMethod | None = None,
    limit: int = Query(100, le=500), offset: int = 0,
    _: User = Depends(require(Permission.LOGS_VIEW)),
    service: JournalService = Depends(get_journal_service),
):
    return service.search(
        employee_id=employee_id, department_id=department_id, entity_id=entity_id,
        zone_id=zone_id, unit_id=unit_id, agent_id=agent_id, checkpoint_id=checkpoint_id,
        verdict=verdict, direction=direction,
        date_from=date_from, date_to=date_to, limit=limit, offset=offset, flag=flag, method=method,
    )


@router.post("/logs/purge", response_model=PurgeOut)
def purge_logs(body: PurgeIn, request: Request, actor: User = Depends(require(Permission.DATA_PURGE)),
               session=Depends(get_session), service: JournalService = Depends(get_journal_service)):
    """``dry_run`` gives the number of lines first (preview), then the real call deletes them."""
    from app.controllers.export_controller import _exporter, describe_journal_filters  # avoids an import cycle

    filters = body.model_dump(exclude={"dry_run"})
    described = describe_journal_filters(session, _exporter(request), filters)
    if body.before is not None:
        described.append("Avant le " + _exporter(request).local(body.before).strftime("%d/%m/%Y"))
    deleted = service.purge(actor.id, filters, described, body.dry_run)
    return PurgeOut(deleted=deleted, dry_run=body.dry_run, filters=described)


def audit_filters(
    action: str | None = Query(None, max_length=80, description="Préfixe : badge, employee, user..."),
    actor_id: int | None = None,
    system: bool = Query(False, description="Seulement les actions sans auteur connecté (téléphones)"),
    target: str | None = Query(None, max_length=120, description="Objet contenant ce texte"),
    date_from: AwareDatetime | None = None, date_to: AwareDatetime | None = None,
) -> AuditFilters:
    return AuditFilters(action=action or None, actor_id=actor_id, system_only=system, target=target,
                        date_from=date_from, date_to=date_to)


@router.get("/audit", response_model=list[AuditOut])
def list_audit(filters: AuditFilters = Depends(audit_filters),
               limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
               _: User = Depends(require(Permission.AUDIT_VIEW)),
               service: AuditService = Depends(get_audit)):
    """Newest first, with author name and IP; never modifiable (FR-72)."""
    return service.search(filters, limit, offset)


@router.get("/audit/actors", response_model=list[AuditActorOut])
def audit_actors(_: User = Depends(require(Permission.AUDIT_VIEW)),
                 service: AuditService = Depends(get_audit)):
    """Authors present in the audit, for the filter."""
    return service.actors()
