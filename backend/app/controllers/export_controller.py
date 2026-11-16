"""Exports: journal / audit / employees in Excel or printable PDF, and the badge to print.

Each export needs the matching *view* right **and** data.export, applies exactly the screen
filters, and is written in the audit (author, type, format, filters, number of rows).
"""
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, Response

from app.controllers.deps import (
    get_audit,
    get_badge_service,
    get_journal_service,
    get_qr_renderer,
    get_session,
    require,
    require_all,
)
from app.controllers.journal_controller import audit_filters
from app.core.exceptions import DomainError
from app.domain.enums import BadgeStatus, Direction, EmployeeStatus, Flag, ScanMethod, Verdict
from app.domain.permissions import Permission
from app.models import AccessLog, Agent, Checkpoint, Department, Employee, Entity, Unit, User, Zone
from app.repositories import repositories as r
from app.services.audit_labels import audit_category_label, audit_label, describe_detail
from app.services.audit_service import AuditFilters, AuditService
from app.services.badge_service import BadgeService
from app.services.export_service import (
    DIRECTION_LABEL,
    FLAG_LABEL,
    QR_BORDER,
    VERDICT_LABEL,
    Column,
    Exporter,
    ExportTable,
    badge_pdf,
    join_flags,
)
from app.services.journal_service import JournalService
from app.services.qr_image import QrImageRenderer

router = APIRouter(tags=["exports"])
METHOD_LABEL = {ScanMethod.QR: "QR", ScanMethod.MANUAL: "Matricule saisi", ScanMethod.CONSOLE: "Console"}
MAX_ROWS = 50_000
Format = Literal["xlsx", "pdf"]
MEDIA = {"xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "pdf": "application/pdf"}

JOURNAL_COLUMNS = [
    Column("Date et heure", lambda line: line.occurred_at, 30),
    Column("Matricule", lambda line: line.employee_matricule, 22),
    Column("Nom", lambda line: line.employee_name or ("QR non reconnu" if line.employee is None else ""), 36),
    Column("Entité", lambda line: line.employee.entity_name if line.employee else None, 26),
    Column("Département", lambda line: line.employee.department_name if line.employee else None, 28),
    Column("Unité", lambda line: line.unit_name, 28),
    Column("Zone", lambda line: line.zone_name, 26),
    Column("Poste", lambda line: line.checkpoint_name, 28),
    Column("Sens", lambda line: DIRECTION_LABEL[line.direction], 19),
    Column("Agent", lambda line: line.agent_name, 26),
    Column("Résultat", lambda line: VERDICT_LABEL[line.verdict], 34),
    Column("Alertes", lambda line: join_flags(line.flags), 30),
    Column("Motif", lambda line: line.reason, 28),
    Column("Saisie", lambda line: METHOD_LABEL[line.method], 20),
]

AUDIT_COLUMNS = [
    Column("Date et heure", lambda e: e.occurred_at, 32),
    Column("Auteur", lambda e: e.actor_name, 30),
    Column("Action", lambda e: audit_label(e.action), 34),
    Column("Objet", lambda e: e.target, 34),
    Column("Détail", lambda e: describe_detail(e.detail), 120),
    Column("Adresse IP", lambda e: e.ip, 22),
]

EMPLOYEE_COLUMNS = [
    Column("Matricule", lambda e: e.matricule, 24),
    Column("Nom", lambda e: e.last_name, 30),
    Column("Prénom", lambda e: e.first_name, 30),
    Column("Fonction", lambda e: e.job_title, 32),
    Column("Entité", lambda e: e.entity_name, 30),
    Column("Département", lambda e: e.department_name, 32),
    Column("Statut", lambda e: {"ACTIF": "Actif", "SUSPENDU": "Suspendu", "ARCHIVE": "Archivé"}[e.status.value], 20),
    Column("Photo", lambda e: "oui" if e.photo_path else "non", 14),
]




def _exporter(request: Request) -> Exporter:
    return Exporter(request.app.state.timezone)


def _send(request: Request, audit: AuditService, actor: User, table: ExportTable, kind: str, fmt: Format,
          filename: str, filters_raw: dict) -> Response:
    exporter = _exporter(request)
    content = exporter.xlsx(table) if fmt == "xlsx" else exporter.pdf(table)
    audit.record(actor.id, f"export.{fmt}", kind, rows=len(table.rows),
                 filters={k: (v.isoformat() if isinstance(v, datetime) else v)
                          for k, v in filters_raw.items() if v is not None})
    stamp = exporter.local(table.generated_at).strftime("%Y%m%d-%H%M")
    return Response(content=content, media_type=MEDIA[fmt],
                    headers={"Content-Disposition": f'attachment; filename="{filename}-{stamp}.{fmt}"'})


def _names(session, model, ids_value: int | None, attribute: str = "name") -> str | None:
    if ids_value is None:
        return None
    item = session.get(model, ids_value)
    return getattr(item, attribute) if item is not None else f"#{ids_value}"


def describe_journal_filters(session, exporter: Exporter, values: dict) -> list[str]:
    """Readable filters, in the order of the screen."""
    out = []
    if values.get("log_ids"):
        out.append(f"{len(values['log_ids'])} passage(s) sélectionné(s)")
    if values.get("date_from"):
        out.append("Du " + exporter.local(values["date_from"]).strftime("%d/%m/%Y"))
    if values.get("date_to"):
        out.append("Au " + exporter.local(values["date_to"]).strftime("%d/%m/%Y"))
    for key, label, model, attribute in (
        ("employee_id", "Employé", Employee, "full_name"), ("entity_id", "Entité", Entity, "name"),
        ("department_id", "Département", Department, "name"), ("unit_id", "Unité", Unit, "name"),
        ("agent_id", "Agent", Agent, "full_name"), ("zone_id", "Zone", Zone, "name"),
        ("checkpoint_id", "Poste", Checkpoint, "name"),
    ):
        name = _names(session, model, values.get(key), attribute)
        if name:
            out.append(f"{label} : {name}")
    if values.get("verdict"):
        out.append("Résultat : " + VERDICT_LABEL[values["verdict"]])
    if values.get("direction"):
        out.append("Sens : " + DIRECTION_LABEL[values["direction"]])
    if values.get("flag"):
        out.append("Alerte : " + FLAG_LABEL[values["flag"].value])
    if values.get("method"):
        out.append("Saisie : " + METHOD_LABEL[values["method"]])
    return out


@router.get("/exports/journal.{fmt}", response_class=Response)
def export_journal(
    request: Request, fmt: Format,
    employee_id: int | None = None, department_id: int | None = None, entity_id: int | None = None,
    zone_id: int | None = None, unit_id: int | None = None, agent_id: int | None = None,
    checkpoint_id: int | None = None, verdict: Verdict | None = None, direction: Direction | None = None,
    date_from: datetime | None = None, date_to: datetime | None = None,
    flag: Flag | None = None, method: ScanMethod | None = None,
    log_ids: list[int] | None = Query(None),
    actor: User = Depends(require_all(Permission.LOGS_VIEW, Permission.DATA_EXPORT)),
    journal: JournalService = Depends(get_journal_service), audit: AuditService = Depends(get_audit),
    session=Depends(get_session),
):
    filters = {"employee_id": employee_id, "department_id": department_id, "entity_id": entity_id,
               "zone_id": zone_id, "unit_id": unit_id, "agent_id": agent_id, "checkpoint_id": checkpoint_id,
               "verdict": verdict, "direction": direction, "date_from": date_from, "date_to": date_to,
               "flag": flag, "method": method, "log_ids": log_ids}
    rows: list[AccessLog] = journal.search(**filters, limit=MAX_ROWS)
    table = ExportTable("Journal des passages", JOURNAL_COLUMNS, rows,
                        describe_journal_filters(session, _exporter(request), filters), actor.full_name,
                        request.app.state.clock.now())
    return _send(request, audit, actor, table, "journal", fmt, "journal-passages", filters)


@router.get("/exports/audit.{fmt}", response_class=Response)
def export_audit(
    request: Request, fmt: Format, filters: AuditFilters = Depends(audit_filters),
    actor: User = Depends(require_all(Permission.AUDIT_VIEW, Permission.DATA_EXPORT)),
    audit: AuditService = Depends(get_audit), session=Depends(get_session),
):
    """Same filters as the audit screen."""
    entries = audit.search(filters, limit=MAX_ROWS)
    exporter = _exporter(request)
    described = []
    if filters.action:
        described.append(f"Catégorie : {audit_category_label(filters.action)}")
    if filters.system_only:
        described.append("Auteur : téléphones / système")
    elif filters.actor_id is not None:
        described.append(f"Auteur : {_names(session, User, filters.actor_id, 'full_name')}")
    if filters.target:
        described.append(f"Objet contenant : {filters.target}")
    if filters.date_from:
        described.append(f"Du {exporter.local(filters.date_from).strftime('%d/%m/%Y')}")
    if filters.date_to:
        described.append(f"Au {exporter.local(filters.date_to).strftime('%d/%m/%Y')}")
    table = ExportTable("Journal d'audit", AUDIT_COLUMNS, entries, described, actor.full_name,
                        request.app.state.clock.now())
    return _send(request, audit, actor, table, "audit", fmt, "audit", {
        "action": filters.action, "actor_id": filters.actor_id, "system": filters.system_only or None,
        "target": filters.target, "date_from": filters.date_from, "date_to": filters.date_to})


@router.get("/exports/employees.{fmt}", response_class=Response)
def export_employees(
    request: Request, fmt: Format, q: str | None = None, status: EmployeeStatus | None = None,
    actor: User = Depends(require_all(Permission.EMPLOYEES_VIEW, Permission.DATA_EXPORT)),
    audit: AuditService = Depends(get_audit), session=Depends(get_session),
):
    rows = r.EmployeeRepository(session).search(q, MAX_ROWS, 0, status)
    described = ([f"Recherche : {q}"] if q else []) + [
        "Statut : " + ({"ACTIF": "actifs", "SUSPENDU": "suspendus", "ARCHIVE": "archivés"}[status.value]
                       if status else "actifs et suspendus")]
    table = ExportTable("Liste des employés", EMPLOYEE_COLUMNS, rows, described, actor.full_name,
                        request.app.state.clock.now())
    return _send(request, audit, actor, table, "employees", fmt, "employes", {"q": q, "status": status})


@router.get("/badges/{badge_id}/print.pdf", response_class=Response)
def print_badge(badge_id: int, request: Request, actor: User = Depends(require(Permission.BADGES_ISSUE)),
                service: BadgeService = Depends(get_badge_service),
                renderer: QrImageRenderer = Depends(get_qr_renderer), audit: AuditService = Depends(get_audit)):
    """Printable badge (FR-50): QR (logo in the centre) + matricule only, at real size with cut marks."""
    badge = service.get(badge_id)
    if badge.status != BadgeStatus.ACTIVE:
        raise DomainError("Badge révoqué : émettez un nouveau badge pour l'imprimer")
    matricule = service.matricule_of(badge)
    qr = renderer.render_qr(service.qr_token(badge_id), border=QR_BORDER)
    pdf = badge_pdf(qr, matricule, request.app.state.qr_logo_path)
    audit.record(actor.id, "badge.print", matricule, version=badge.version)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="badge-{matricule}-v{badge.version}.pdf"'})
