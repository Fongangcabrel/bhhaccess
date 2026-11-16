"""Manual unblock of a person stuck by a strict anti-passback zone."""
from enum import StrEnum

from app.core.clock import Clock
from app.core.exceptions import DomainError, NotFoundError
from app.domain.enums import Direction, ScanMethod, Verdict
from app.models import AccessLog, ZonePresence
from app.repositories.repositories import (
    AccessLogRepository,
    CheckpointRepository,
    EmployeeRepository,
    PresenceRepository,
    ZoneRepository,
)
from app.services.audit_service import AuditService


class UnblockMode(StrEnum):
    EXIT = "sortie"    # default: clear the "inside" state so the person may enter again
    ENTRY = "entree"   # record a manual entry (person is in fact inside)


class PresenceService:
    def __init__(self, presences: PresenceRepository, employees: EmployeeRepository,
                 zones: ZoneRepository, checkpoints: CheckpointRepository,
                 logs: AccessLogRepository, audit: AuditService, clock: Clock) -> None:
        self._presences = presences
        self._employees = employees
        self._zones = zones
        self._checkpoints = checkpoints
        self._logs = logs
        self._audit = audit
        self._clock = clock

    def unblock(self, actor_id: int, employee_id: int, zone_id: int,
                mode: UnblockMode, reason: str) -> None:
        if not reason.strip():
            raise DomainError("Un motif est obligatoire")
        employee = self._employees.get_locked(employee_id)
        zone = self._zones.get(zone_id)
        if employee is None or zone is None:
            raise NotFoundError("Employé ou zone introuvable")
        checkpoint = self._any_checkpoint(zone_id, Direction.EXIT if mode == UnblockMode.EXIT else Direction.ENTRY)

        now = self._clock.now()
        presence = self._presences.get_locked(employee_id, zone_id)
        state_before = "in" if presence is not None else "out"
        if mode == UnblockMode.EXIT and presence is not None:
            self._presences.remove(presence)
        elif mode == UnblockMode.ENTRY and presence is None:
            self._presences.add(ZonePresence(employee_id=employee_id, zone_id=zone_id,
                                             entered_at=now, checkpoint_id=checkpoint.id))
        verdict = Verdict.EXIT_RECORDED if mode == UnblockMode.EXIT else Verdict.AUTHORIZED
        self._logs.add(AccessLog(
            occurred_at=now, employee_id=employee_id, zone_id=zone_id,
            checkpoint_id=checkpoint.id, direction=checkpoint.direction, verdict=verdict,
            flags=[], method=ScanMethod.CONSOLE, operator_id=actor_id, reason=reason,
        ))
        self._audit.record(actor_id, "presence.unblock", employee.matricule,
                           zone=zone.name, mode=mode.value, reason=reason,
                           before={"state": state_before},
                           after={"state": "out" if mode == UnblockMode.EXIT else "in"})

    def _any_checkpoint(self, zone_id: int, direction: Direction):
        for checkpoint in self._checkpoints.list(limit=1000):
            if checkpoint.zone_id == zone_id and checkpoint.direction == direction:
                return checkpoint
        raise NotFoundError("La zone n'a aucun point de contrôle pour ce sens")
