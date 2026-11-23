"""Reports over a period (tâche 32, SRS FR-73 and FR-77).

* Movements: entries, exits and refusals per employee and per zone (FR-73).
* Presence by zone: who is inside now, how many people came in, entries / exits / refusals (FR-77).
* Refusal trends: refusals day by day, by reason, by zone and the people refused most (FR-77).

Every report takes the journal filters (period, employee, department, entity, unit, zone) and is
computed in SQL from the immutable journal. Only real passages at a post count as entries and
exits: a console unblock is counted apart ("Déblocages"), it is a correction, not a passage.
"""
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.core.clock import Clock
from app.core.exceptions import DomainError
from app.domain.enums import AntiPassbackMode
from app.repositories.repositories import (
    REFUSED_VERDICTS,
    AccessLogRepository,
    EmployeeRepository,
    PresenceRepository,
    ZoneRepository,
)

TREND_DEFAULT_DAYS = 30
TREND_MAX_DAYS = 366
TOP_EMPLOYEES = 10


@dataclass(frozen=True)
class ReportFilters:
    date_from: datetime | None = None
    date_to: datetime | None = None
    employee_id: int | None = None
    department_id: int | None = None
    entity_id: int | None = None
    unit_id: int | None = None
    zone_id: int | None = None

    def query(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class MovementRow:
    employee_id: int
    matricule: str
    full_name: str
    entity_name: str | None
    department_name: str | None
    unit_name: str
    zone_id: int
    zone_name: str
    entries: int
    exits: int
    refused: int
    unblocks: int
    first_at: datetime
    last_at: datetime


@dataclass
class MovementReport:
    rows: list[MovementRow]
    employees: int
    entries: int
    exits: int
    refused: int
    unblocks: int


@dataclass
class ZonePresenceRow:
    unit_name: str
    zone_id: int
    zone_name: str
    mode: AntiPassbackMode
    inside_now: int | None  # None: zone in "Libre" mode, no presence is kept
    people: int
    entries: int
    exits: int
    refused: int


@dataclass
class PresenceReport:
    rows: list[ZonePresenceRow]
    inside_now: int
    entries: int
    exits: int
    refused: int


@dataclass
class TrendDay:
    day: date
    total: int
    by_verdict: dict[str, int]


@dataclass
class CountByZone:
    zone_id: int
    zone_name: str
    unit_name: str
    count: int


@dataclass
class CountByEmployee:
    employee_id: int
    matricule: str
    full_name: str
    count: int


@dataclass
class RefusalTrend:
    date_from: datetime
    date_to: datetime
    total: int
    previous_total: int  # same length, just before: is it getting better or worse?
    days: list[TrendDay]
    by_verdict: dict[str, int]
    by_zone: list[CountByZone] = field(default_factory=list)
    by_employee: list[CountByEmployee] = field(default_factory=list)
    unknown_qr: int = 0  # refusals with nobody behind them (QR non reconnu)


class PeriodReportService:
    def __init__(self, logs: AccessLogRepository, presences: PresenceRepository, employees: EmployeeRepository,
                 zones: ZoneRepository, clock: Clock, timezone: str) -> None:
        self._logs = logs
        self._presences = presences
        self._employees = employees
        self._zones = zones
        self._clock = clock
        self._tz = ZoneInfo(timezone)

    def normalize(self, filters: ReportFilters) -> ReportFilters:
        """A date without time zone is read as site local time (never a 500)."""
        def aware(value: datetime | None) -> datetime | None:
            return value.replace(tzinfo=self._tz) if value is not None and value.tzinfo is None else value

        start, end = aware(filters.date_from), aware(filters.date_to)
        if start is not None and end is not None and start > end:
            raise DomainError("La date de début doit précéder la date de fin")
        return ReportFilters(start, end, filters.employee_id, filters.department_id, filters.entity_id,
                             filters.unit_id, filters.zone_id)

    # --- FR-73 -------------------------------------------------------------------
    def movements(self, filters: ReportFilters) -> MovementReport:
        filters = self.normalize(filters)
        grouped = self._logs.movements(**filters.query())
        people = self._employees.get_many({g.employee_id for g in grouped})
        zones = self._zones.get_many({g.zone_id for g in grouped})
        rows = []
        for g in grouped:
            employee, zone = people[g.employee_id], zones[g.zone_id]
            rows.append(MovementRow(
                employee_id=employee.id, matricule=employee.matricule, full_name=employee.full_name,
                entity_name=employee.entity_name, department_name=employee.department_name,
                unit_name=zone.unit.name, zone_id=zone.id, zone_name=zone.name,
                entries=g.entries, exits=g.exits, refused=g.refused, unblocks=g.unblocks,
                first_at=g.first_at, last_at=g.last_at))
        rows.sort(key=lambda row: (row.full_name.casefold(), row.matricule, row.unit_name, row.zone_name))
        return MovementReport(rows=rows, employees=len({row.employee_id for row in rows}),
                              entries=sum(r.entries for r in rows), exits=sum(r.exits for r in rows),
                              refused=sum(r.refused for r in rows), unblocks=sum(r.unblocks for r in rows))

    # --- FR-77: presence by zone -----------------------------------------------------
    def presence(self, filters: ReportFilters) -> PresenceReport:
        filters = self.normalize(filters)
        activity = {a.zone_id: a for a in self._logs.zone_activity(**filters.query())}
        inside = self._presences.count_by_zone(department_id=filters.department_id, entity_id=filters.entity_id)
        rows = []
        for zone in self._zones.list(limit=5000):
            if filters.zone_id is not None and zone.id != filters.zone_id:
                continue
            if filters.unit_id is not None and zone.unit_id != filters.unit_id:
                continue
            a = activity.get(zone.id)
            if a is None and not zone.is_active:
                continue  # an inactive zone with nothing in the period is noise
            tracked = zone.antipassback_mode != AntiPassbackMode.DISABLED
            rows.append(ZonePresenceRow(
                unit_name=zone.unit.name, zone_id=zone.id, zone_name=zone.name, mode=zone.antipassback_mode,
                inside_now=inside.get(zone.id, 0) if tracked else None,
                people=a.people if a else 0, entries=a.entries if a else 0,
                exits=a.exits if a else 0, refused=a.refused if a else 0))
        rows.sort(key=lambda row: (row.unit_name.casefold(), row.zone_name.casefold()))
        return PresenceReport(rows=rows, inside_now=sum(r.inside_now or 0 for r in rows),
                              entries=sum(r.entries for r in rows), exits=sum(r.exits for r in rows),
                              refused=sum(r.refused for r in rows))

    # --- FR-77: refusal trends -----------------------------------------------------
    def refusal_trend(self, filters: ReportFilters) -> RefusalTrend:
        filters = self.normalize(filters)
        end = filters.date_to or self._clock.now()
        first_day = (filters.date_from.astimezone(self._tz).date() if filters.date_from
                     else end.astimezone(self._tz).date() - timedelta(days=TREND_DEFAULT_DAYS - 1))
        start = filters.date_from or datetime.combine(first_day, time.min, self._tz)
        last_day = end.astimezone(self._tz).date()
        if (last_day - first_day).days + 1 > TREND_MAX_DAYS:
            raise DomainError("Période trop longue : 366 jours maximum pour les tendances")
        filters = ReportFilters(start, end, filters.employee_id, filters.department_id, filters.entity_id,
                                filters.unit_id, filters.zone_id)

        per_day: dict[date, Counter] = defaultdict(Counter)
        by_verdict: Counter = Counter()
        by_zone: Counter = Counter()
        by_employee: Counter = Counter()
        unknown = 0
        for occurred_at, verdict, zone_id, employee_id in self._logs.refusals(**filters.query()):
            per_day[occurred_at.astimezone(self._tz).date()][verdict.value] += 1
            by_verdict[verdict.value] += 1
            by_zone[zone_id] += 1
            if employee_id is None:
                unknown += 1
            else:
                by_employee[employee_id] += 1

        days = []
        day = first_day
        while day <= last_day:  # every day of the period, empty days included: a trend needs them
            counts = per_day.get(day, Counter())
            days.append(TrendDay(day=day, total=sum(counts.values()), by_verdict=dict(counts)))
            day += timedelta(days=1)

        length = end - start
        previous = ReportFilters(start - length, start - timedelta(microseconds=1), filters.employee_id,
                                 filters.department_id, filters.entity_id, filters.unit_id, filters.zone_id)
        zones = self._zones.get_many(by_zone.keys())
        top = by_employee.most_common(TOP_EMPLOYEES)
        people = self._employees.get_many(employee_id for employee_id, _ in top)
        return RefusalTrend(
            date_from=start, date_to=end, total=sum(by_verdict.values()),
            previous_total=self._logs.count_refusals(**previous.query()),
            days=days,
            by_verdict={v.value: by_verdict[v.value] for v in REFUSED_VERDICTS if by_verdict[v.value]},
            by_zone=[CountByZone(zone_id, zones[zone_id].name, zones[zone_id].unit.name, count)
                     for zone_id, count in by_zone.most_common()],
            by_employee=[CountByEmployee(employee_id, people[employee_id].matricule, people[employee_id].full_name,
                                         count) for employee_id, count in top],
            unknown_qr=unknown,
        )

