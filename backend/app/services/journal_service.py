from datetime import datetime

from app.core.exceptions import DomainError
from app.domain.enums import Direction, Flag, ScanMethod, Verdict
from app.models import AccessLog
from app.repositories.repositories import AccessLogRepository
from app.services.audit_service import AuditService


class JournalService:
    def __init__(self, logs: AccessLogRepository, audit: AuditService) -> None:
        self._logs = logs
        self._audit = audit

    def search(self, *, employee_id: int | None = None, department_id: int | None = None,
               entity_id: int | None = None, zone_id: int | None = None, unit_id: int | None = None,
               agent_id: int | None = None,
               checkpoint_id: int | None = None, verdict: Verdict | None = None,
               direction: Direction | None = None, date_from: datetime | None = None,
               date_to: datetime | None = None, limit: int = 100, offset: int = 0,
               flag: Flag | None = None, method: ScanMethod | None = None,
               log_ids: list[int] | None = None) -> list[AccessLog]:
        return self._logs.search(
            employee_id=employee_id, department_id=department_id, entity_id=entity_id,
            zone_id=zone_id, unit_id=unit_id, agent_id=agent_id, checkpoint_id=checkpoint_id,
            verdict=verdict, direction=direction,
            date_from=date_from, date_to=date_to, limit=limit, offset=offset, flag=flag, method=method,
            log_ids=log_ids,
        )

    def purge(self, actor_id: int, filters: dict, described: list[str], dry_run: bool) -> int:
        """Bulk delete (data.purge, FR-97/98). ``dry_run`` only counts the lines (the preview).
        The purge itself is audited (author, filters, number of lines) and the audit is permanent."""
        filters = {k: v for k, v in filters.items() if v is not None}
        if not filters:
            raise DomainError("Choisissez au moins un filtre (période, employé, département, entité ou zone)")
        if dry_run:
            return self._logs.count_matching(**filters)
        deleted = self._logs.delete_matching(**filters)
        self._audit.record(actor_id, "logs.purge", "; ".join(described) or None, deleted=deleted,
                           filters={k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in filters.items()})
        return deleted
