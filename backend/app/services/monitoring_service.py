"""Live supervision: who is inside / who left, zone by zone and unit by unit (tâche 12).

Where everybody stands is rebuilt from the journal of the last 24 hours, so it works for every
zone, whatever its entry control mode: the last movement of a person in a zone decides
(authorised entry -> inside, exit -> left). For zones whose mode keeps a presence state
("Signalé" / "Sortie obligatoire"), that state is authoritative: it also knows manual unblocks
and people who came in more than 24 hours ago.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.clock import Clock
from app.domain.enums import AntiPassbackMode, Direction, EmployeeStatus, Verdict
from app.models import AccessLog, Checkpoint, Employee, Unit
from app.repositories.repositories import AccessLogRepository, CheckpointRepository, PresenceRepository, UnitRepository

WINDOW = timedelta(hours=24)
RECENT_REFUSALS = 10
_REFUSALS = {v for v in Verdict if v.value.startswith("REFUSE_")}
_UNIT_SUMS = ("inside", "exited", "entries", "exits", "refused", "anomalies")


@dataclass
class _State:
    inside: bool
    at: datetime
    checkpoint: str
    employee: Employee


@dataclass
class _ZoneCounters:
    entries: int = 0
    exits: int = 0
    refused: int = 0
    anomalies: int = 0
    last_activity: datetime | None = None


@dataclass
class _PostCounters:
    scans: int = 0
    last_scan: datetime | None = None


@dataclass
class _Totals:
    entries: int = 0
    exits: int = 0
    refused: int = 0
    unknown_qr: int = 0
    anomalies: int = 0
    flags: Counter = field(default_factory=Counter)


class MonitoringService:
    def __init__(self, logs: AccessLogRepository, presences: PresenceRepository, units: UnitRepository,
                 checkpoints: CheckpointRepository, clock: Clock, timezone: str) -> None:
        self._logs = logs
        self._presences = presences
        self._units = units
        self._checkpoints = checkpoints
        self._clock = clock
        self._tz = ZoneInfo(timezone)

    def snapshot(self, unit_id: int | None = None) -> dict:
        now = self._clock.now()
        today = now.astimezone(self._tz).replace(hour=0, minute=0, second=0, microsecond=0)
        lines = self._logs.since(now - WINDOW)

        states: dict[tuple[int, int], _State] = {}
        zones: dict[int, _ZoneCounters] = defaultdict(_ZoneCounters)
        posts: dict[int, _PostCounters] = defaultdict(_PostCounters)
        totals = _Totals()
        refusals: list[AccessLog] = []
        for line in lines:  # oldest first
            zone = zones[line.zone_id]
            zone.last_activity = line.occurred_at
            if line.employee is not None and line.verdict in (Verdict.AUTHORIZED, Verdict.EXIT_RECORDED):
                states[(line.employee_id, line.zone_id)] = _State(
                    inside=line.verdict == Verdict.AUTHORIZED and line.direction == Direction.ENTRY,
                    at=line.occurred_at, checkpoint=line.checkpoint.name, employee=line.employee)
            if line.occurred_at < today:
                continue
            post = posts[line.checkpoint_id]
            post.scans += 1
            post.last_scan = line.occurred_at
            if line.verdict == Verdict.AUTHORIZED:
                zone.entries += 1
                totals.entries += 1
            elif line.verdict == Verdict.EXIT_RECORDED:
                zone.exits += 1
                totals.exits += 1
            elif line.verdict in _REFUSALS:
                zone.refused += 1
                totals.refused += 1
                totals.unknown_qr += line.verdict == Verdict.DENIED_INVALID
                refusals.append(line)
            if line.flags:
                zone.anomalies += 1
                totals.anomalies += 1
                totals.flags.update(line.flags)

        tracked = {}  # zones with a presence state: that state decides who is inside
        for presence in self._presences.inside(None):
            tracked.setdefault(presence.zone_id, []).append(presence)

        units_out = []
        inside_total = 0
        for unit in self._units.all():
            if unit_id is not None and unit.id != unit_id:
                continue
            unit_out = self._unit(unit, states, zones, tracked, today)
            inside_total += unit_out["inside"]
            units_out.append(unit_out)

        return {
            "generated_at": now,
            "since": today,
            "totals": {
                "entries": totals.entries, "exits": totals.exits, "refused": totals.refused,
                "unknown_qr": totals.unknown_qr, "anomalies": totals.anomalies, "inside": inside_total,
                "exited": sum(u["exited"] for u in units_out),
                "flags": dict(totals.flags),
            },
            "units": units_out,
            "posts": self._posts(posts, unit_id),
            "recent_refusals": [self._refusal(line) for line in reversed(refusals[-RECENT_REFUSALS:])],
        }

    # --- building blocks ---------------------------------------------------------
    def _unit(self, unit: Unit, states, zones, tracked, today: datetime) -> dict:
        zones_out = []
        for zone in unit.zones:
            counters = zones[zone.id]
            inside, exited = [], []
            if zone.antipassback_mode != AntiPassbackMode.DISABLED:
                for presence in tracked.get(zone.id, []):
                    if presence.employee.status != EmployeeStatus.ARCHIVED:
                        state = states.get((presence.employee_id, zone.id))
                        inside.append(_person(presence.employee, presence.entered_at,
                                              state.checkpoint if state else None))
            for (employee_id, zone_id), state in states.items():
                if zone_id != zone.id or state.employee.status == EmployeeStatus.ARCHIVED:
                    continue
                if state.inside and zone.antipassback_mode == AntiPassbackMode.DISABLED:
                    inside.append(_person(state.employee, state.at, state.checkpoint))
                elif not state.inside and state.at >= today and employee_id not in {p["employee_id"] for p in inside}:
                    exited.append(_person(state.employee, state.at, state.checkpoint))
            inside.sort(key=lambda p: p["at"], reverse=True)
            exited.sort(key=lambda p: p["at"], reverse=True)
            zones_out.append({
                "zone_id": zone.id, "zone_name": zone.name, "code": zone.code, "mode": zone.antipassback_mode,
                "is_active": zone.is_active, "inside": len(inside), "exited": len(exited),
                "entries": counters.entries, "exits": counters.exits, "refused": counters.refused,
                "anomalies": counters.anomalies, "last_activity": counters.last_activity,
                "people_inside": inside, "people_exited": exited,
            })
        return {
            "unit_id": unit.id, "unit_name": unit.name, "zones": zones_out,
            **{key: sum(z[key] for z in zones_out) for key in _UNIT_SUMS},
        }

    def _posts(self, counters: dict[int, _PostCounters], unit_id: int | None) -> list[dict]:
        out = []
        for checkpoint in self._checkpoints.list(limit=10_000):
            if unit_id is not None and checkpoint.zone.unit_id != unit_id:
                continue
            c = counters.get(checkpoint.id, _PostCounters())
            out.append({
                "checkpoint_id": checkpoint.id, "checkpoint_name": checkpoint.name, "direction": checkpoint.direction,
                "zone_name": checkpoint.zone.name, "unit_name": checkpoint.zone.unit.name,
                "usable": checkpoint.usable, "agent_name": _agent(checkpoint),
                "scans_today": c.scans, "last_scan": c.last_scan,
            })
        out.sort(key=lambda p: (p["unit_name"], p["zone_name"], p["direction"] != Direction.ENTRY,
                                p["checkpoint_name"]))
        return out

    @staticmethod
    def _refusal(line: AccessLog) -> dict:
        employee = line.employee
        return {
            "log_id": line.id, "at": line.occurred_at, "verdict": line.verdict,
            "employee_name": employee.full_name if employee else None,
            "matricule": employee.matricule if employee else None,
            "zone_name": line.zone.name, "checkpoint_name": line.checkpoint.name,
            "agent_name": line.agent_name, "reason": line.reason,
        }


def _person(employee: Employee, at: datetime, checkpoint: str | None) -> dict:
    return {
        "employee_id": employee.id, "full_name": employee.full_name, "matricule": employee.matricule,
        "department_name": employee.department_name, "at": at, "checkpoint_name": checkpoint,
    }


def _agent(checkpoint: Checkpoint) -> str | None:
    return checkpoint.agent_name
