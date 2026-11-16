from datetime import datetime

from sqlalchemy.exc import IntegrityError

from app.core.clock import Clock
from app.core.exceptions import ConflictError, DomainError, NotFoundError
from app.domain.enums import BadgeStatus, EmployeeStatus, RevocationReason
from app.domain.qr_token import TokenSigner
from app.models import Badge
from app.repositories.repositories import BadgeRepository, EmployeeRepository
from app.services.audit_service import AuditService


class BadgeService:
    def __init__(self, badges: BadgeRepository, employees: EmployeeRepository,
                 signer: TokenSigner, audit: AuditService, clock: Clock) -> None:
        self._badges = badges
        self._employees = employees
        self._signer = signer
        self._audit = audit
        self._clock = clock

    def issue(self, actor_id: int, employee_id: int, expires_at: datetime | None) -> Badge:
        """Issue a badge to an ACTIVE employee (SRS FR-50); the previous active one is revoked.

        The employee row is locked so that two simultaneous issues are serialised, and the
        partial unique index ``one_active_badge`` is the last line of defence (FR-51).
        """
        employee = self._employees.get_locked(employee_id)
        if employee is None:
            raise NotFoundError("Employé introuvable")
        if employee.status == EmployeeStatus.ARCHIVED:
            raise DomainError("Employé archivé : restaurez-le avant d'émettre un badge")
        if employee.status != EmployeeStatus.ACTIVE:
            raise DomainError("Employé suspendu : réactivez-le avant d'émettre un badge")
        now = self._clock.now()
        if expires_at is not None and expires_at <= now:
            raise DomainError("La date d'expiration doit être dans le futur")
        replaced = []
        for current in self._badges.all_active_for_employee(employee_id):
            self._close(current, actor_id, RevocationReason.REPLACED, None, now)
            replaced.append(current.version)
        self._badges.flush()  # the old badge leaves the unique index before the new one enters
        try:
            badge = self._badges.add(
                Badge(
                    employee_id=employee_id, issued_at=now, expires_at=expires_at,
                    version=self._badges.latest_version(employee_id) + 1,
                )
            )
        except IntegrityError as exc:  # pragma: no cover - only under a real race
            raise ConflictError("Un badge vient d'être émis pour cet employé : rechargez la fiche") from exc
        self._audit.record(actor_id, "badge.issue", employee.matricule, version=badge.version,
                           replaced_versions=replaced)
        return badge

    def revoke(self, actor_id: int, badge_id: int, reason: RevocationReason, note: str | None = None) -> Badge:
        """Revoke with a reason (FR-52). « Autre » needs a short explanation. Never reactivated."""
        note = (note or "").strip() or None
        if reason == RevocationReason.OTHER and note is None:
            raise DomainError("Précisez le motif lorsque vous choisissez « Autre »")
        if reason == RevocationReason.REPLACED:
            raise DomainError("« Remplacement » est posé automatiquement à la réémission : choisissez un autre motif")
        badge = self.get(badge_id)
        if badge.status != BadgeStatus.ACTIVE:
            raise ConflictError("Ce badge est déjà révoqué")
        self._close(badge, actor_id, reason, note, self._clock.now())
        self._badges.flush()
        self._audit.record(actor_id, "badge.revoke", self.matricule_of(badge), badge_id=badge.id,
                           version=badge.version, reason=reason.value, note=note)
        return badge

    @staticmethod
    def _close(badge: Badge, actor_id: int | None, reason: RevocationReason, note: str | None,
               now: datetime) -> None:
        badge.status, badge.revoked_at = BadgeStatus.REVOKED, now
        badge.revoked_reason, badge.revoked_note, badge.revoked_by = reason, note, actor_id

    def get(self, badge_id: int) -> Badge:
        badge = self._badges.get(badge_id)
        if badge is None:
            raise NotFoundError("Badge introuvable")
        return badge

    def qr_token(self, badge_id: int) -> str:
        badge = self.get(badge_id)
        return self._signer.sign(badge.id, badge.version, badge.issued_at)

    def matricule_of(self, badge: Badge) -> str:
        return self._employees.get(badge.employee_id).matricule
