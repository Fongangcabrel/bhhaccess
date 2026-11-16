"""Read endpoints that feed the back-office screens."""
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Response

from app.controllers.deps import (
    get_audit,
    get_journal_service,
    get_monitoring_service,
    get_report_service,
    get_session,
    require,
    require_all,
)
from app.domain.enums import Direction, Flag, ScanMethod, Verdict
from app.domain.permissions import Permission
from app.models import User
from app.repositories import repositories as r
from app.schemas.dto import (
    AuthorizationOut,
    BadgeOut,
    DepartmentOut,
    EntityOut,
    MonitoringOut,
    PresenceOut,
    StatsOut,
)
from app.services.audit_service import AuditService
from app.services.journal_service import JournalService
from app.services.monitoring_service import MonitoringService
from app.services.report_service import ReportService

router = APIRouter(tags=["back-office"])


@router.get("/org/entities", response_model=list[EntityOut])
def list_entities(_: User = Depends(require(Permission.EMPLOYEES_VIEW)), session=Depends(get_session)):
    return r.EntityRepository(session).list(limit=500)


@router.get("/org/departments", response_model=list[DepartmentOut])
def list_departments(_: User = Depends(require(Permission.EMPLOYEES_VIEW)), session=Depends(get_session)):
    return r.DepartmentRepository(session).list(limit=500)


@router.get("/employees/{employee_id}/badges", response_model=list[BadgeOut])
def employee_badges(employee_id: int, _: User = Depends(require(Permission.EMPLOYEES_VIEW)),
                    session=Depends(get_session)):
    return r.BadgeRepository(session).for_employee(employee_id)


@router.get("/employees/{employee_id}/authorizations", response_model=list[AuthorizationOut])
def employee_authorizations(employee_id: int, _: User = Depends(require(Permission.EMPLOYEES_VIEW)),
                            session=Depends(get_session)):
    return r.AuthorizationRepository(session).for_employee(employee_id)


@router.get("/presence", response_model=list[PresenceOut])
def who_is_inside(zone_id: int | None = None, _: User = Depends(require(Permission.LOGS_VIEW)),
                  service: ReportService = Depends(get_report_service)):
    return [
        PresenceOut(employee_id=p.employee_id, matricule=p.employee.matricule, full_name=p.employee.full_name,
                    zone_id=p.zone_id, zone_name=p.zone.name, entered_at=p.entered_at)
        for p in service.inside(zone_id)
    ]


@router.get("/monitoring", response_model=MonitoringOut)
def monitoring(unit_id: int | None = None, _: User = Depends(require(Permission.LOGS_VIEW)),
               service: MonitoringService = Depends(get_monitoring_service)):
    """Live supervision: inside / left by unit and zone, today's counters, posts, latest refusals."""
    return service.snapshot(unit_id)


@router.get("/stats/today", response_model=StatsOut)
def stats_today(_: User = Depends(require(Permission.LOGS_VIEW)),
                service: ReportService = Depends(get_report_service)):
    return service.stats_today()


@router.get("/logs/export.csv")
def export_logs(
    employee_id: int | None = None, department_id: int | None = None, entity_id: int | None = None,
    zone_id: int | None = None, unit_id: int | None = None, agent_id: int | None = None,
    checkpoint_id: int | None = None,
    verdict: Verdict | None = None, direction: Direction | None = None,
    date_from: datetime | None = None, date_to: datetime | None = None,
    flag: Flag | None = None, method: ScanMethod | None = None,
    limit: int = Query(20000, le=50000),
    actor: User = Depends(require_all(Permission.LOGS_VIEW, Permission.DATA_EXPORT)),
    journal: JournalService = Depends(get_journal_service),
    reports: ReportService = Depends(get_report_service),
    audit: AuditService = Depends(get_audit),
):
    rows = journal.search(
        employee_id=employee_id, department_id=department_id, entity_id=entity_id, zone_id=zone_id,
        unit_id=unit_id, agent_id=agent_id, checkpoint_id=checkpoint_id, verdict=verdict, direction=direction,
        date_from=date_from, date_to=date_to, limit=limit, flag=flag, method=method,
    )
    audit.record(actor.id, "export.csv", "journal", rows=len(rows))
    return Response(
        content=reports.logs_to_csv(rows), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="journal-acces.csv"'},
    )
