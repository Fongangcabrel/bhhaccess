"""Bulk changes on employees (SRS FR-28) and zones given to a whole department (FR-42).

The employees are either a selection (``employee_ids``) or everybody currently on staff in a
department and/or an entity. Each change goes through the usual service (same checks, same audit
line per employee); a refused employee is reported and the others are still done. Every check of
those services runs before any change, so a refusal never leaves a half-done employee. One more
audit line sums up the batch.
"""
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError, NotFoundError
from app.domain.enums import BulkAction, EmployeeStatus
from app.domain.permissions import Permission
from app.models import Department, Employee, Entity, Zone
from app.repositories.repositories import AuthorizationRepository
from app.services.audit_service import AuditService
from app.services.employee_service import EmployeeService
from app.services.zone_service import ZoneService

MAX_EMPLOYEES = 1000


RIGHT = {
    BulkAction.ORG: Permission.EMPLOYEES_EDIT,
    BulkAction.SUSPEND: Permission.EMPLOYEES_EDIT,
    BulkAction.REACTIVATE: Permission.EMPLOYEES_EDIT,
    BulkAction.ARCHIVE: Permission.EMPLOYEES_ARCHIVE,
    BulkAction.ADD_ZONES: Permission.AUTHORIZATIONS_MANAGE,
    BulkAction.REMOVE_ZONES: Permission.AUTHORIZATIONS_MANAGE,
}


@dataclass
class Failure:
    employee_id: int
    matricule: str
    reason: str


@dataclass
class BulkResult:
    action: BulkAction
    total: int = 0
    done: list[int] = field(default_factory=list)
    unchanged: list[int] = field(default_factory=list)
    failed: list[Failure] = field(default_factory=list)


class BulkService:
    def __init__(self, session: Session, employees: EmployeeService, zones: ZoneService, audit: AuditService) -> None:
        self._session = session
        self._employees = employees
        self._zones = zones
        self._authorizations = AuthorizationRepository(session)
        self._audit = audit

    # --- who ----------------------------------------------------------------------
    def targets(self, employee_ids: list[int] | None, department_id: int | None,
                entity_id: int | None) -> tuple[list[Employee], str]:
        """The employees concerned, and how to name them in the audit."""
        if employee_ids:
            ids = list(dict.fromkeys(employee_ids))
            if len(ids) > MAX_EMPLOYEES:
                raise DomainError(f"Trop d'employés : {MAX_EMPLOYEES} maximum")
            found = {e.id: e for e in self._session.scalars(select(Employee).where(Employee.id.in_(ids)))}
            if len(found) != len(ids):
                raise NotFoundError("Employé introuvable")
            return [found[i] for i in ids], f"{len(ids)} employé(s) sélectionné(s)"
        if department_id is None and entity_id is None:
            raise DomainError("Choisissez des employés, un département ou une entité")
        stmt = select(Employee).where(Employee.status != EmployeeStatus.ARCHIVED).order_by(Employee.last_name)
        labels = []
        if department_id is not None:
            department = self._session.get(Department, department_id)
            if department is None:
                raise NotFoundError("Département introuvable")
            stmt = stmt.where(Employee.department_id == department_id)
            labels.append(f"département {department.name}")
        if entity_id is not None:
            entity = self._session.get(Entity, entity_id)
            if entity is None:
                raise NotFoundError("Entité introuvable")
            stmt = stmt.where(Employee.entity_id == entity_id)
            labels.append(f"entité {entity.name}")
        employees = list(self._session.scalars(stmt))
        if len(employees) > MAX_EMPLOYEES:
            raise DomainError(f"Trop d'employés : {MAX_EMPLOYEES} maximum")
        return employees, " · ".join(labels)

    # --- what ---------------------------------------------------------------------------
    def run(self, actor_id: int, action: BulkAction, employees: list[Employee], target: str, *,
            org_changes: dict | None = None, zone_ids: list[int] | None = None,
            reason: str | None = None) -> BulkResult:
        zones = self._check_inputs(action, org_changes, zone_ids, reason)
        result = BulkResult(action=action, total=len(employees))
        for employee in employees:
            try:
                changed = self._apply(actor_id, action, employee, org_changes or {}, zones, reason or "")
            except DomainError as error:
                result.failed.append(Failure(employee.id, employee.matricule, error.message))
                continue
            (result.done if changed else result.unchanged).append(employee.id)
        self._audit.record(actor_id, "employee.bulk", target, operation=action.value, total=result.total,
                           done=len(result.done), unchanged=len(result.unchanged), failed=len(result.failed),
                           zones=[z.name for z in zones] or None, reason=reason or None,
                           after=dict(org_changes or {}) or None)
        return result

    def _check_inputs(self, action: BulkAction, org_changes: dict | None, zone_ids: list[int] | None,
                      reason: str | None) -> list[Zone]:
        if action == BulkAction.ORG and not org_changes:
            raise DomainError("Choisissez l'entité ou le département à appliquer")
        if action == BulkAction.ARCHIVE and len((reason or "").strip()) < 3:
            raise DomainError("Un motif est obligatoire")
        if action in (BulkAction.ADD_ZONES, BulkAction.REMOVE_ZONES):
            if not zone_ids:
                raise DomainError("Choisissez au moins une zone")
            zones = [self._session.get(Zone, zone_id) for zone_id in dict.fromkeys(zone_ids)]
            if any(zone is None for zone in zones):
                raise NotFoundError("Zone introuvable")
            return zones
        return []

    def _apply(self, actor_id: int, action: BulkAction, employee: Employee, org_changes: dict,
               zones: list[Zone], reason: str) -> bool:
        """True when something changed for this employee."""
        if action == BulkAction.ORG:
            if all(getattr(employee, key) == value for key, value in org_changes.items()):
                return False
            self._employees.update(actor_id, employee.id, org_changes)
            return True
        if action in (BulkAction.SUSPEND, BulkAction.REACTIVATE):
            wanted = EmployeeStatus.SUSPENDED if action == BulkAction.SUSPEND else EmployeeStatus.ACTIVE
            if employee.status == wanted:
                return False
            self._employees.change_status(actor_id, employee.id, wanted)
            return True
        if action == BulkAction.ARCHIVE:
            if employee.status == EmployeeStatus.ARCHIVED:
                return False
            self._employees.archive(actor_id, employee.id, reason)
            return True
        if employee.status == EmployeeStatus.ARCHIVED:
            raise DomainError("Employé archivé : restaurez-le avant de le modifier")
        changed = False
        for zone in zones:
            present = self._authorizations.find(employee.id, zone.id) is not None
            if action == BulkAction.ADD_ZONES and not present:
                self._zones.grant(actor_id, employee.id, zone.id, None)
                changed = True
            elif action == BulkAction.REMOVE_ZONES and present:
                self._zones.revoke_authorization(actor_id, employee.id, zone.id)
                changed = True
        return changed
