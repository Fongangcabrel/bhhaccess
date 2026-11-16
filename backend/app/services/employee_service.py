"""Employee lifecycle: create, edit, suspend / reactivate, archive / restore.

Archiving replaces deletion: the person leaves the current lists, every active badge is
revoked (an old QR never comes back), the "inside" states are cleared, but the history and
the zone authorisations are kept so that a restore brings the file back as it was
(App Flow 3.5). An archived employee's QR reads "QR non reconnu" at the gate.
"""
from typing import TYPE_CHECKING

from app.core.clock import Clock
from app.core.exceptions import ConflictError, DomainError, NotFoundError
from app.domain.enums import BadgeStatus, EmployeeStatus, RevocationReason
from app.models import Employee
from app.repositories.repositories import BadgeRepository, EmployeeRepository, PresenceRepository
from app.services.audit_service import AuditService

if TYPE_CHECKING:
    from app.services.org_service import OrgService

EDITABLE_FIELDS = ("matricule", "last_name", "first_name", "job_title", "entity_id", "department_id", "extra")


class EmployeeService:
    def __init__(self, employees: EmployeeRepository, badges: BadgeRepository, presences: PresenceRepository,
                 audit: AuditService, clock: Clock, org: "OrgService | None" = None) -> None:
        self._org = org
        self._employees = employees
        self._badges = badges
        self._presences = presences
        self._audit = audit
        self._clock = clock

    def create(self, actor_id: int, *, matricule: str, last_name: str, first_name: str,
               job_title: str | None, entity_id: int | None, department_id: int | None,
               extra: dict | None) -> Employee:
        matricule = matricule.strip()
        if self._employees.by_matricule(matricule):
            raise ConflictError(f"Matricule déjà utilisé : {matricule}")
        if self._org is not None:
            self._org.check_assignment(entity_id, department_id)
        employee = self._employees.add(
            Employee(
                matricule=matricule, last_name=last_name.strip(), first_name=first_name.strip(),
                job_title=job_title, entity_id=entity_id, department_id=department_id,
                extra=extra or {},
            )
        )
        self._audit.record(actor_id, "employee.create", matricule)
        return employee

    def get(self, employee_id: int) -> Employee:
        employee = self._employees.get(employee_id)
        if employee is None:
            raise NotFoundError("Employé introuvable")
        return employee

    def search(self, text: str | None, limit: int, offset: int,
               status: EmployeeStatus | None = None) -> list[Employee]:
        return self._employees.search(text, limit, offset, status)

    def update(self, actor_id: int, employee_id: int, changes: dict) -> Employee:
        """Edit the identity fields given in ``changes``; the audit keeps old and new values."""
        employee = self.get(employee_id)
        if employee.status == EmployeeStatus.ARCHIVED:
            raise DomainError("Employé archivé : restaurez-le avant de le modifier")
        changes = {k: v for k, v in changes.items() if k in EDITABLE_FIELDS}
        for key in ("matricule", "last_name", "first_name"):
            if key in changes:
                changes[key] = (changes[key] or "").strip()
                if not changes[key]:
                    raise DomainError("Matricule, nom et prénom sont obligatoires")
        new_matricule = changes.get("matricule")
        if new_matricule and new_matricule != employee.matricule:
            other = self._employees.by_matricule(new_matricule)
            if other is not None and other.id != employee.id:
                raise ConflictError(f"Matricule déjà utilisé : {new_matricule}")
        if self._org is not None and ("entity_id" in changes or "department_id" in changes):
            self._org.check_assignment(changes.get("entity_id", employee.entity_id),
                                       changes.get("department_id", employee.department_id))
        before, after = {}, {}
        for key, value in changes.items():
            if getattr(employee, key) != value:
                before[key], after[key] = getattr(employee, key), value
                setattr(employee, key, value)
        if after:
            self._employees.flush()
            self._audit.record(actor_id, "employee.update", employee.matricule, before=before, after=after)
        return employee

    def change_status(self, actor_id: int, employee_id: int, status: EmployeeStatus) -> Employee:
        """Suspend or reactivate. Archiving has its own action (motif, badges revoked)."""
        if status == EmployeeStatus.ARCHIVED:
            raise DomainError("Utilisez l'action « Archiver », qui demande un motif")
        employee = self.get(employee_id)
        if employee.status == EmployeeStatus.ARCHIVED:
            raise DomainError("Employé archivé : utilisez « Restaurer »")
        previous = employee.status
        employee.status = status
        self._audit.record(actor_id, "employee.status", employee.matricule,
                           before={"status": previous.value}, after={"status": status.value})
        return employee

    def archive(self, actor_id: int, employee_id: int, reason: str) -> Employee:
        reason = reason.strip()
        if not reason:
            raise DomainError("Un motif est obligatoire")
        employee = self._employees.get_locked(employee_id)  # no scan of this person in between
        if employee is None:
            raise NotFoundError("Employé introuvable")
        if employee.status == EmployeeStatus.ARCHIVED:
            raise ConflictError("Employé déjà archivé")
        now = self._clock.now()
        revoked = []
        for badge in self._badges.all_active_for_employee(employee.id):
            badge.status, badge.revoked_at = BadgeStatus.REVOKED, now
            badge.revoked_reason, badge.revoked_by = RevocationReason.DEPARTURE, actor_id
            badge.revoked_note = f"Archivage : {reason}"[:300]
            revoked.append(badge.version)
        cleared = self._presences.clear_employee(employee.id)
        previous = employee.status
        employee.status = EmployeeStatus.ARCHIVED
        employee.archived_at, employee.archived_by, employee.archive_reason = now, actor_id, reason
        self._employees.flush()
        self._audit.record(actor_id, "employee.archive", employee.matricule, reason=reason,
                           old=previous.value, badges_revoked=revoked, presences_cleared=cleared)
        return employee

    def restore(self, actor_id: int, employee_id: int) -> Employee:
        """Back to active with file, zones and history. No badge is issued: a new one is needed."""
        employee = self.get(employee_id)
        if employee.status != EmployeeStatus.ARCHIVED:
            raise ConflictError("Cet employé n'est pas archivé")
        archived_at, reason = employee.archived_at, employee.archive_reason
        employee.status = EmployeeStatus.ACTIVE
        employee.archived_at = employee.archived_by = employee.archive_reason = None
        self._employees.flush()
        self._audit.record(actor_id, "employee.restore", employee.matricule,
                           archived_at=archived_at.isoformat() if archived_at else None, archive_reason=reason)
        return employee
