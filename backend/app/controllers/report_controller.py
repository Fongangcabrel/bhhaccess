"""Reports over a period (tâche 32): movements, presence by zone, refusal trends, and their exports.

Reading needs reports.view; Excel / PDF also need data.export and are written in the audit.
"""

from fastapi import APIRouter, Depends, Request, Response
from pydantic import AwareDatetime

from app.controllers.deps import get_audit, get_period_report_service, get_session, require, require_all
from app.controllers.export_controller import Format, _exporter, _send, describe_journal_filters
from app.domain.enums import AntiPassbackMode, Verdict
from app.domain.permissions import Permission
from app.models import User
from app.repositories.repositories import REFUSED_VERDICTS
from app.schemas.dto import MovementReportOut, PresenceReportOut, RefusalTrendOut
from app.services.audit_service import AuditService
from app.services.export_service import VERDICT_LABEL, Column, ExportTable
from app.services.period_report_service import PeriodReportService, ReportFilters, TrendDay

router = APIRouter(tags=["reports"])

MODE_LABEL = {AntiPassbackMode.DISABLED: "Libre", AntiPassbackMode.SOFT: "Signalé",
              AntiPassbackMode.STRICT: "Sortie obligatoire"}

MOVEMENT_COLUMNS = [
    Column("Matricule", lambda m: m.matricule, 22),
    Column("Nom", lambda m: m.full_name, 34),
    Column("Entité", lambda m: m.entity_name, 26),
    Column("Département", lambda m: m.department_name, 28),
    Column("Unité", lambda m: m.unit_name, 26),
    Column("Zone", lambda m: m.zone_name, 26),
    Column("Entrées", lambda m: m.entries, 16),
    Column("Sorties", lambda m: m.exits, 16),
    Column("Refus", lambda m: m.refused, 14),
    Column("Déblocages", lambda m: m.unblocks, 18),
    Column("Premier passage", lambda m: m.first_at, 30),
    Column("Dernier passage", lambda m: m.last_at, 30),
]

PRESENCE_COLUMNS = [
    Column("Unité", lambda z: z.unit_name, 30),
    Column("Zone", lambda z: z.zone_name, 30),
    Column("Contrôle des entrées", lambda z: MODE_LABEL[z.mode], 30),
    Column("À l'intérieur maintenant", lambda z: "non suivi" if z.inside_now is None else z.inside_now, 26),
    Column("Personnes entrées", lambda z: z.people, 22),
    Column("Entrées", lambda z: z.entries, 16),
    Column("Sorties", lambda z: z.exits, 16),
    Column("Refus", lambda z: z.refused, 14),
]


def _verdict_column(verdict: Verdict) -> Column:
    return Column(VERDICT_LABEL[verdict].removeprefix("Refusé : ").capitalize(),
                  lambda d: d.by_verdict.get(verdict.value, 0), 22)


TREND_COLUMNS = [
    Column("Jour", lambda d: d.day.strftime("%d/%m/%Y"), 20),
    Column("Refus", lambda d: d.total, 14),
    *(_verdict_column(v) for v in REFUSED_VERDICTS),
]


def report_filters(
    date_from: AwareDatetime | None = None, date_to: AwareDatetime | None = None,
    employee_id: int | None = None, department_id: int | None = None, entity_id: int | None = None,
    unit_id: int | None = None, zone_id: int | None = None,
) -> ReportFilters:
    return ReportFilters(date_from, date_to, employee_id, department_id, entity_id, unit_id, zone_id)


@router.get("/reports/movements", response_model=MovementReportOut)
def movements(filters: ReportFilters = Depends(report_filters),
              _: User = Depends(require(Permission.REPORTS_VIEW)),
              service: PeriodReportService = Depends(get_period_report_service)):
    """Entries, exits and refusals per employee and per zone over the period (FR-73)."""
    return service.movements(filters)


@router.get("/reports/presence", response_model=PresenceReportOut)
def presence(filters: ReportFilters = Depends(report_filters),
             _: User = Depends(require(Permission.REPORTS_VIEW)),
             service: PeriodReportService = Depends(get_period_report_service)):
    """Per zone: inside now, people who came in, entries / exits / refusals over the period (FR-77)."""
    return service.presence(filters)


@router.get("/reports/refusals", response_model=RefusalTrendOut)
def refusals(filters: ReportFilters = Depends(report_filters),
             _: User = Depends(require(Permission.REPORTS_VIEW)),
             service: PeriodReportService = Depends(get_period_report_service)):
    """Refusals day by day, by reason, by zone and by person (FR-77). 30 days by default, 366 max."""
    return service.refusal_trend(filters)


# --- exports ---------------------------------------------------------------------------
_EXPORT_RIGHTS = require_all(Permission.REPORTS_VIEW, Permission.DATA_EXPORT)


def _table(request: Request, session, title: str, columns: list[Column], rows: list, filters: ReportFilters,
           actor: User) -> ExportTable:
    described = describe_journal_filters(session, _exporter(request), filters.query())
    return ExportTable(title, columns, rows, described, actor.full_name, request.app.state.clock.now())


@router.get("/exports/movements.{fmt}", response_class=Response)
def export_movements(request: Request, fmt: Format, filters: ReportFilters = Depends(report_filters),
                     actor: User = Depends(_EXPORT_RIGHTS), session=Depends(get_session),
                     service: PeriodReportService = Depends(get_period_report_service),
                     audit: AuditService = Depends(get_audit)):
    filters = service.normalize(filters)
    report = service.movements(filters)
    table = _table(request, session, "Mouvements par employé et par zone", MOVEMENT_COLUMNS, report.rows,
                   filters, actor)
    return _send(request, audit, actor, table, "movements", fmt, "mouvements", filters.query())


@router.get("/exports/presence.{fmt}", response_class=Response)
def export_presence(request: Request, fmt: Format, filters: ReportFilters = Depends(report_filters),
                    actor: User = Depends(_EXPORT_RIGHTS), session=Depends(get_session),
                    service: PeriodReportService = Depends(get_period_report_service),
                    audit: AuditService = Depends(get_audit)):
    filters = service.normalize(filters)
    report = service.presence(filters)
    table = _table(request, session, "Présence par zone", PRESENCE_COLUMNS, report.rows, filters, actor)
    return _send(request, audit, actor, table, "presence", fmt, "presence-par-zone", filters.query())


@router.get("/exports/refusals.{fmt}", response_class=Response)
def export_refusals(request: Request, fmt: Format, filters: ReportFilters = Depends(report_filters),
                    actor: User = Depends(_EXPORT_RIGHTS), session=Depends(get_session),
                    service: PeriodReportService = Depends(get_period_report_service),
                    audit: AuditService = Depends(get_audit)):
    trend = service.refusal_trend(filters)
    period = ReportFilters(trend.date_from, trend.date_to, filters.employee_id, filters.department_id,
                           filters.entity_id, filters.unit_id, filters.zone_id)  # the period actually shown
    rows: list[TrendDay] = trend.days
    table = _table(request, session, "Tendances des refus", TREND_COLUMNS, rows, period, actor)
    table.filters.append(f"Total : {trend.total} refus (période précédente : {trend.previous_total})")
    return _send(request, audit, actor, table, "refusals", fmt, "tendances-refus", period.query())
