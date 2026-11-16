from datetime import datetime

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

    def purge_before(self, actor_id: int, cutoff: datetime) -> int:
        """Bulk delete (data.purge). The purge itself is audited and the audit is permanent."""
        deleted = self._logs.purge_before(cutoff)
        self._audit.record(actor_id, "logs.purge", None, before=cutoff.isoformat(), deleted=deleted)
        return deleted
