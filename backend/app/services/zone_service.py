"""Units, zones, checkpoints and the employees' zone authorisations.

Editing and deleting follow one rule: something the journal (or the agents' history) refers
to is never deleted, it is deactivated instead, so that past passages stay readable.
"""
from datetime import datetime, time
from zoneinfo import ZoneInfo

from app.core.clock import Clock, SystemClock
from app.core.exceptions import ConflictError, DomainError, NotFoundError
from app.domain import access_window
from app.domain.enums import AntiPassbackMode, Direction, ZoneSensitivity
from app.models import AccessSchedule, Checkpoint, Unit, Zone, ZoneAuthorization
from app.repositories.repositories import (
    AccessLogRepository,
    AssignmentRepository,
    AuthorizationRepository,
    CheckpointRepository,
    EmployeeRepository,
    PresenceRepository,
    UnitRepository,
    ZoneRepository,
)
from app.services.audit_service import AuditService

DEFAULT_UNIT = "Général"
ZONE_FIELDS = ("name", "code", "description", "sensitivity", "is_active")
CHECKPOINT_FIELDS = ("name", "direction", "is_active")


def _clean(text: str | None) -> str | None:
    text = (text or "").strip()
    return text or None


def _diff(entity, changes: dict) -> tuple[dict, dict]:
    """Apply ``changes`` to ``entity``; return (before, after) of what really changed."""
    before, after = {}, {}
    for key, value in changes.items():
        old = getattr(entity, key)
        if old != value:
            before[key], after[key] = old, value
            setattr(entity, key, value)
    return before, after


class ZoneService:
    def __init__(self, zones: ZoneRepository, checkpoints: CheckpointRepository,
                 authorizations: AuthorizationRepository, employees: EmployeeRepository,
                 units: UnitRepository, audit: AuditService, logs: AccessLogRepository,
                 assignments: AssignmentRepository, presences: PresenceRepository,
                 clock: Clock | None = None, timezone: str = "Africa/Douala") -> None:
        self._clock = clock or SystemClock()
        self._tz = ZoneInfo(timezone)
        self._units = units
        self._zones = zones
        self._checkpoints = checkpoints
        self._authorizations = authorizations
        self._employees = employees
        self._audit = audit
        self._logs = logs
        self._assignments = assignments
        self._presences = presences

    # --- units -------------------------------------------------------------
    def create_unit(self, actor_id: int, name: str) -> Unit:
        name = name.strip()
        if not name:
            raise DomainError("Nom d'unité obligatoire")
        if self._units.by_name(name):
            raise ConflictError(f"Unité déjà existante : {name}")
        unit = self._units.add(Unit(name=name))
        self._audit.record(actor_id, "unit.create", name)
        return unit

    def rename_unit(self, actor_id: int, unit_id: int, name: str) -> Unit:
        unit, name = self._require_unit(unit_id), name.strip()
        if not name:
            raise DomainError("Nom d'unité obligatoire")
        other = self._units.by_name(name)
        if other is not None and other.id != unit.id:
            raise ConflictError(f"Unité déjà existante : {name}")
        old, unit.name = unit.name, name
        self._units.flush()
        self._audit.record(actor_id, "unit.rename", name, before={"name": old}, after={"name": name})
        return unit

    def delete_unit(self, actor_id: int, unit_id: int) -> None:
        unit = self._require_unit(unit_id)
        if unit.zones:
            raise ConflictError("Cette unité contient des zones : déplacez-les ou supprimez-les d'abord")
        self._units.remove(unit)
        self._audit.record(actor_id, "unit.delete", unit.name)

    def list_units(self) -> list[Unit]:
        return self._units.all()

    def move_zone(self, actor_id: int, zone_id: int, unit_id: int) -> Zone:
        zone, unit = self._require_zone(zone_id), self._require_unit(unit_id)
        old = zone.unit.name if zone.unit else None
        zone.unit_id = unit.id
        zone.unit = unit
        self._audit.record(actor_id, "zone.move", zone.name, before={"unit": old}, after={"unit": unit.name})
        return zone

    # --- zones -------------------------------------------------------------
    def create_zone(self, actor_id: int, name: str, mode: AntiPassbackMode,
                    unit_id: int | None = None, *, code: str | None = None, description: str | None = None,
                    sensitivity: ZoneSensitivity = ZoneSensitivity.STANDARD, warn_agent: bool = False) -> Zone:
        name, code = name.strip(), _clean(code.upper() if code else None)
        if not name:
            raise DomainError("Nom de zone obligatoire")
        if self._zones.by_name(name):
            raise ConflictError(f"Zone déjà existante : {name}")
        if code and self._zones.by_code(code):
            raise ConflictError(f"Code de zone déjà utilisé : {code}")
        unit = self._require_unit(unit_id) if unit_id is not None else self._default_unit(actor_id)
        zone = self._zones.add(Zone(name=name, code=code, description=_clean(description), sensitivity=sensitivity,
                                    antipassback_mode=mode, unit_id=unit.id,
                                    antipassback_warn_agent=warn_agent and mode == AntiPassbackMode.SOFT))
        self._audit.record(actor_id, "zone.create", name, mode=mode.value, unit=unit.name,
                           warn_agent=zone.antipassback_warn_agent)
        return zone

    def update_zone(self, actor_id: int, zone_id: int, changes: dict) -> Zone:
        """Name, code, description, sensitivity, active flag. The control mode has its own right."""
        zone = self._require_zone(zone_id)
        changes = {k: v for k, v in changes.items() if k in ZONE_FIELDS}
        if "name" in changes:
            changes["name"] = (changes["name"] or "").strip()
            if not changes["name"]:
                raise DomainError("Nom de zone obligatoire")
            other = self._zones.by_name(changes["name"])
            if other is not None and other.id != zone.id:
                raise ConflictError(f"Zone déjà existante : {changes['name']}")
        if "code" in changes:
            changes["code"] = _clean(changes["code"].upper() if changes["code"] else None)
            other = self._zones.by_code(changes["code"]) if changes["code"] else None
            if other is not None and other.id != zone.id:
                raise ConflictError(f"Code de zone déjà utilisé : {changes['code']}")
        if "description" in changes:
            changes["description"] = _clean(changes["description"])
        before, after = _diff(zone, changes)
        if after:
            self._zones.flush()
            self._audit.record(actor_id, "zone.update", zone.name, before=_jsonable(before), after=_jsonable(after))
        return zone

    def delete_zone(self, actor_id: int, zone_id: int) -> None:
        """Only a zone that never saw a passage; otherwise deactivate it to keep the journal readable."""
        zone = self._require_zone(zone_id)
        if self._logs.used_by(zone_id=zone.id):
            raise ConflictError("Cette zone a un historique de passages : désactivez-la plutôt")
        checkpoints = self._checkpoints.for_zone(zone.id)
        if any(self._assignments.used_by(checkpoint_id=c.id) for c in checkpoints):
            raise ConflictError("Des agents ont déjà été postés dans cette zone : désactivez-la plutôt")
        for checkpoint in checkpoints:
            self._checkpoints.remove(checkpoint)
        removed = self._authorizations.delete_for_zone(zone.id)
        self._presences.clear_zone(zone.id)
        self._zones.remove(zone)
        self._audit.record(actor_id, "zone.delete", zone.name, checkpoints=len(checkpoints),
                           authorizations_removed=removed)

    def set_mode(self, actor_id: int, zone_id: int, mode: AntiPassbackMode,
                 warn_agent: bool | None = None) -> Zone:
        """The warning option only exists in « Signalé » (SOUPLE): it is cleared in the other modes."""
        zone = self._require_zone(zone_id)
        before = {"mode": zone.antipassback_mode.value, "warn_agent": zone.antipassback_warn_agent}
        zone.antipassback_mode = mode
        if warn_agent is not None:
            zone.antipassback_warn_agent = warn_agent
        if mode != AntiPassbackMode.SOFT:
            zone.antipassback_warn_agent = False
        self._audit.record(actor_id, "zone.antipassback", zone.name, before=before,
                           after={"mode": mode.value, "warn_agent": zone.antipassback_warn_agent})
        return zone

    def list_zones(self) -> list[Zone]:
        return self._zones.list(limit=10_000)

    # --- checkpoints -------------------------------------------------------
    def add_checkpoint(self, actor_id: int, zone_id: int, name: str, direction: Direction) -> Checkpoint:
        zone, name = self._require_zone(zone_id), name.strip()
        if not name:
            raise DomainError("Nom du poste obligatoire")
        checkpoint = self._checkpoints.add(Checkpoint(name=name, zone_id=zone.id, direction=direction))
        self._audit.record(actor_id, "checkpoint.create", name, zone=zone.name)
        return checkpoint

    def update_checkpoint(self, actor_id: int, checkpoint_id: int, changes: dict) -> Checkpoint:
        checkpoint = self._require_checkpoint(checkpoint_id)
        changes = {k: v for k, v in changes.items() if k in CHECKPOINT_FIELDS}
        if "name" in changes:
            changes["name"] = (changes["name"] or "").strip()
            if not changes["name"]:
                raise DomainError("Nom du poste obligatoire")
        before, after = _diff(checkpoint, changes)
        if after:
            self._checkpoints.flush()
            self._audit.record(actor_id, "checkpoint.update", checkpoint.name, zone=checkpoint.zone.name,
                               before=_jsonable(before), after=_jsonable(after))
        return checkpoint

    def delete_checkpoint(self, actor_id: int, checkpoint_id: int) -> None:
        checkpoint = self._require_checkpoint(checkpoint_id)
        if self._logs.used_by(checkpoint_id=checkpoint.id):
            raise ConflictError("Ce poste a un historique de passages : désactivez-le plutôt")
        if self._assignments.used_by(checkpoint_id=checkpoint.id):
            raise ConflictError("Des agents ont déjà tenu ce poste : désactivez-le plutôt")
        self._checkpoints.remove(checkpoint)
        self._audit.record(actor_id, "checkpoint.delete", checkpoint.name, zone=checkpoint.zone.name)

    def list_checkpoints(self, usable_only: bool = False) -> list[Checkpoint]:
        checkpoints = self._checkpoints.list(limit=10_000)
        return [c for c in checkpoints if c.usable] if usable_only else checkpoints

    # --- authorisations ----------------------------------------------------
    def grant(self, actor_id: int, employee_id: int, zone_id: int,
              valid_until: datetime | None) -> ZoneAuthorization:
        employee = self._employees.get(employee_id)
        if employee is None:
            raise NotFoundError("Employé introuvable")
        zone = self._require_zone(zone_id)
        authorization = self._authorizations.find(employee_id, zone_id)
        before = None if authorization is None else {"valid_until": _jsonable(authorization.valid_until)}
        if authorization is None:
            authorization = self._authorizations.add(
                ZoneAuthorization(employee_id=employee_id, zone_id=zone_id, valid_until=valid_until)
            )
        else:
            authorization.valid_until = valid_until
        self._audit.record(actor_id, "authorization.grant", employee.matricule, zone=zone.name,
                           before=before or {"zones": None}, after={"valid_until": _jsonable(valid_until)}
                           if before else {"zones": zone.name})
        return authorization

    def revoke_authorization(self, actor_id: int, employee_id: int, zone_id: int) -> None:
        authorization = self._authorizations.find(employee_id, zone_id)
        if authorization is None:
            raise NotFoundError("Autorisation introuvable")
        employee, zone = self._employees.get(employee_id), self._zones.get(zone_id)
        self._authorizations.remove(authorization)
        self._audit.record(actor_id, "authorization.revoke",
                           employee.matricule if employee else str(employee_id),
                           zone=zone.name if zone else zone_id)

    # --- employee access, configured per unit -------------------------------
    def employee_access(self, employee_id: int) -> list[dict]:
        """Every unit with its zones; a unit where nothing is ticked is 'REFUSE'."""
        if self._employees.get(employee_id) is None:
            raise NotFoundError("Employé introuvable")
        granted = {a.zone_id: a for a in self._authorizations.for_employee(employee_id)}
        now = self._clock.now()
        result = []
        for unit in self._units.all():
            zones = [{"id": z.id, "name": z.name, "granted": z.id in granted, "is_active": z.is_active,
                      **self._restrictions_view(granted.get(z.id), now)}
                     for z in unit.zones]
            result.append({"unit_id": unit.id, "unit_name": unit.name,
                           "status": "ACCES" if any(z["granted"] for z in zones) else "REFUSE",
                           "zones": zones})
        return result

    def set_employee_access(self, actor_id: int, employee_id: int, zone_ids: list[int]) -> list[dict]:
        """Replace the employee's zones by exactly ``zone_ids`` (kept ones keep their expiry date)."""
        employee = self._employees.get(employee_id)
        if employee is None:
            raise NotFoundError("Employé introuvable")
        wanted = set(zone_ids)
        known = {z.id for z in self._zones.list(limit=10_000)}
        if wanted - known:
            raise NotFoundError("Zone introuvable")
        current = {a.zone_id: a for a in self._authorizations.for_employee(employee_id)}
        for zone_id, authorization in current.items():
            if zone_id not in wanted:
                self._authorizations.remove(authorization)
        for zone_id in wanted - current.keys():
            self._authorizations.add(ZoneAuthorization(employee_id=employee_id, zone_id=zone_id, valid_until=None,
                                                       granted_by=actor_id))
        names = {z.id: z.name for z in self._zones.list(limit=10_000)}
        label = lambda ids: sorted(names[i] for i in ids)  # noqa: E731
        self._audit.record(actor_id, "authorization.set", employee.matricule,
                           added=label(wanted - current.keys()), removed=label(current.keys() - wanted),
                           before={"zones": label(current.keys())}, after={"zones": label(wanted)})
        return self.employee_access(employee_id)

    def set_restrictions(self, actor_id: int, employee_id: int, zone_id: int, valid_from: datetime | None,
                         valid_until: datetime | None, schedules: list[tuple[list[int], time, time]]) -> dict:
        """Dates and weekly slots of one ticked zone (SRS FR-43, PRD F11). Replaces what was there."""
        employee = self._employees.get(employee_id)
        zone = self._require_zone(zone_id)
        authorization = self._authorizations.find(employee_id, zone_id)
        if employee is None or authorization is None:
            raise NotFoundError("Cochez et enregistrez d'abord cette zone pour l'employé")
        if valid_from and valid_until and valid_until <= valid_from:
            raise DomainError("La date de fin doit être après la date de début")
        for days, _start, _end in schedules:
            if any(d < 1 or d > 7 for d in days):
                raise DomainError("Jours invalides : 1 = lundi … 7 = dimanche")
        before = self._summary(authorization)
        authorization.valid_from, authorization.valid_until = valid_from, valid_until
        authorization.schedules[:] = [
            AccessSchedule(weekdays=sorted(set(days)), start_time=start.replace(second=0, microsecond=0),
                           end_time=end.replace(second=0, microsecond=0))
            for days, start, end in schedules
        ]
        self._authorizations.flush()
        after = self._summary(authorization)
        self._audit.record(actor_id, "authorization.restrict", employee.matricule, zone=zone.name,
                           before={"restrictions": before or "permanent"},
                           after={"restrictions": after or "permanent"})
        return {"id": zone.id, "name": zone.name, "granted": True, "is_active": zone.is_active,
                **self._restrictions_view(authorization, self._clock.now())}

    def _summary(self, authorization: ZoneAuthorization) -> str:
        return access_window.describe(authorization.valid_from, authorization.valid_until, authorization.slots,
                                      self._tz)

    def _restrictions_view(self, authorization: ZoneAuthorization | None, now: datetime) -> dict:
        if authorization is None:
            return {}
        return {
            "valid_from": authorization.valid_from, "valid_until": authorization.valid_until,
            "schedules": [{"weekdays": s.weekdays, "start": s.start_time, "end": s.end_time}
                          for s in authorization.schedules],
            "restrictions": self._summary(authorization),
            "usable_now": access_window.check(now, self._tz, authorization.valid_from, authorization.valid_until,
                                              authorization.slots) is None,
        }

    # --- internals ---------------------------------------------------------
    def _default_unit(self, actor_id: int) -> Unit:
        return self._units.by_name(DEFAULT_UNIT) or self.create_unit(actor_id, DEFAULT_UNIT)

    def _require_unit(self, unit_id: int) -> Unit:
        unit = self._units.get(unit_id)
        if unit is None:
            raise NotFoundError("Unité introuvable")
        return unit

    def _require_zone(self, zone_id: int) -> Zone:
        zone = self._zones.get(zone_id)
        if zone is None:
            raise NotFoundError("Zone introuvable")
        return zone

    def _require_checkpoint(self, checkpoint_id: int) -> Checkpoint:
        checkpoint = self._checkpoints.get(checkpoint_id)
        if checkpoint is None:
            raise NotFoundError("Point de contrôle introuvable")
        return checkpoint


def _jsonable(values: dict) -> dict:
    """Enums -> their value, so the audit JSON stays readable."""
    return {k: getattr(v, "value", v) for k, v in values.items()}
