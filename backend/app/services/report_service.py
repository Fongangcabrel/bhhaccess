"""Read-only views for the dashboard and exports."""
import csv
from datetime import datetime
from io import StringIO
from zoneinfo import ZoneInfo

from app.core.clock import Clock
from app.domain.enums import Verdict
from app.models import AccessLog, ZonePresence
from app.repositories.repositories import AccessLogRepository, PresenceRepository
from app.services.export_service import safe_text

_REFUSALS = {v for v in Verdict if v.value.startswith("REFUSE_")}


class ReportService:
    def __init__(self, logs: AccessLogRepository, presences: PresenceRepository, clock: Clock, timezone: str) -> None:
        self._logs = logs
        self._presences = presences
        self._clock = clock
        self._tz = ZoneInfo(timezone)

    def stats_today(self) -> dict:
        """Counters since local midnight."""
        now_local = self._clock.now().astimezone(self._tz)
        since = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        counts = self._logs.count_by_verdict(since)
        return {
            "since": since,
            "total": sum(counts.values()),
            "entries_authorized": counts.get(Verdict.AUTHORIZED, 0),
            "exits": counts.get(Verdict.EXIT_RECORDED, 0),
            "refused": sum(n for v, n in counts.items() if v in _REFUSALS),
            "inside": len(self._presences.inside(None)),
            "by_verdict": {v.value: n for v, n in counts.items()},
        }

    def inside(self, zone_id: int | None) -> list[ZonePresence]:
        return self._presences.inside(zone_id)

    def logs_to_csv(self, rows: list[AccessLog]) -> str:
        """CSV readable by Excel (UTF-8 with BOM, ';' separator, local time)."""
        buffer = StringIO()
        writer = csv.writer(buffer, delimiter=";")
        writer.writerow(["Date", "Heure", "Matricule", "Nom", "Entité", "Département", "Unité", "Zone",
                         "Point", "Agent", "Sens", "Verdict", "Alertes", "Motif"])
        for row in rows:
            local: datetime = row.occurred_at.astimezone(self._tz)
            employee = row.employee
            writer.writerow([safe_text(value) for value in (
                local.strftime("%d/%m/%Y"), local.strftime("%H:%M:%S"),
                row.employee_matricule or "", row.employee_name or "",
                (employee.entity_name if employee else "") or "",
                (employee.department_name if employee else "") or "",
                row.unit_name, row.zone_name, row.checkpoint_name, row.agent_name or "",
                row.direction.value, row.verdict.value,
                ", ".join(row.flags), row.reason or "",
            )])
        return "﻿" + buffer.getvalue()
