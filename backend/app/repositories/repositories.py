"""Concrete repositories, one per aggregate."""
from datetime import datetime

from sqlalchemy import String, and_, case, cast, delete, func, select
from sqlalchemy.orm import Session

from app.domain.enums import BadgeStatus, Direction, EmployeeStatus, Flag, ScanMethod, Verdict
from app.models import (
    AccessLog,
    AccessSchedule,
    Agent,
    AgentAssignment,
    AuditEntry,
    Badge,
    Checkpoint,
    Department,
    Device,
    Employee,
    Entity,
    Role,
    Unit,
    User,
    Zone,
    ZoneAuthorization,
    ZonePresence,
)
from app.repositories.base import BaseRepository

REFUSED_VERDICTS = [v for v in Verdict if v.value.startswith("REFUSE_")]
_SCAN = AccessLog.method != ScanMethod.CONSOLE  # a real passage at a post, not a console unblock


def _count(condition):
    return func.coalesce(func.sum(case((condition, 1), else_=0)), 0)


class EntityRepository(BaseRepository[Entity]):
    model = Entity

    def by_name(self, name: str) -> Entity | None:
        return self._session.scalar(select(Entity).where(Entity.name == name))


class DepartmentRepository(BaseRepository[Department]):
    model = Department

    def by_name(self, name: str) -> Department | None:
        """Case-insensitive: « RH » and « rh » are the same department."""
        return self._session.scalar(select(Department).where(func.lower(Department.name) == name.strip().lower()))


class EmployeeRepository(BaseRepository[Employee]):
    model = Employee

    def by_matricule(self, matricule: str) -> Employee | None:
        return self._session.scalar(select(Employee).where(Employee.matricule == matricule))

    def get_locked(self, employee_id: int) -> Employee | None:
        """Row lock on the employee: serialises concurrent scans of the same person.

        Locking the presence row alone is not enough - when it does not exist yet there is
        nothing to lock and two simultaneous entries would both insert.
        """
        stmt = select(Employee).where(Employee.id == employee_id).with_for_update()
        return self._session.scalar(stmt)

    def search(self, text: str | None, limit: int, offset: int,
               status: EmployeeStatus | None = None) -> list[Employee]:
        """``status=None`` lists the current staff (active + suspended): archived people leave the lists."""
        stmt = select(Employee).order_by(Employee.last_name).limit(limit).offset(offset)
        if status is None:
            stmt = stmt.where(Employee.status != EmployeeStatus.ARCHIVED)
        else:
            stmt = stmt.where(Employee.status == status)
        if text:
            like = f"%{text}%"
            stmt = stmt.where(
                (Employee.matricule.ilike(like))
                | (Employee.last_name.ilike(like))
                | (Employee.first_name.ilike(like))
            )
        return list(self._session.scalars(stmt))

    def with_photo(self, *, employee_ids: list[int] | None = None, department_id: int | None = None,
                   entity_id: int | None = None, archived_only: bool = False) -> list[Employee]:
        """Employees that have a photo, matching every filter given."""
        stmt = select(Employee).where(Employee.photo_path.is_not(None)).order_by(Employee.id)
        if employee_ids is not None:
            stmt = stmt.where(Employee.id.in_(employee_ids))
        if department_id is not None:
            stmt = stmt.where(Employee.department_id == department_id)
        if entity_id is not None:
            stmt = stmt.where(Employee.entity_id == entity_id)
        if archived_only:
            stmt = stmt.where(Employee.status == EmployeeStatus.ARCHIVED)
        return list(self._session.scalars(stmt))


class BadgeRepository(BaseRepository[Badge]):
    model = Badge

    def active_for_employee(self, employee_id: int) -> Badge | None:
        stmt = select(Badge).where(
            Badge.employee_id == employee_id, Badge.status == BadgeStatus.ACTIVE
        ).order_by(Badge.version.desc())
        return self._session.scalars(stmt).first()

    def for_employee(self, employee_id: int) -> list[Badge]:
        stmt = select(Badge).where(Badge.employee_id == employee_id).order_by(Badge.version.desc())
        return list(self._session.scalars(stmt))

    def all_active_for_employee(self, employee_id: int) -> list[Badge]:
        stmt = select(Badge).where(Badge.employee_id == employee_id, Badge.status == BadgeStatus.ACTIVE)
        return list(self._session.scalars(stmt))

    def latest_version(self, employee_id: int) -> int:
        stmt = select(Badge.version).where(Badge.employee_id == employee_id).order_by(
            Badge.version.desc()
        )
        return self._session.scalars(stmt).first() or 0


class ZoneRepository(BaseRepository[Zone]):
    model = Zone

    def by_name(self, name: str) -> Zone | None:
        return self._session.scalar(select(Zone).where(Zone.name == name))

    def by_code(self, code: str) -> Zone | None:
        return self._session.scalar(select(Zone).where(Zone.code == code))


class UnitRepository(BaseRepository[Unit]):
    model = Unit

    def by_name(self, name: str) -> Unit | None:
        return self._session.scalar(select(Unit).where(Unit.name == name))

    def all(self) -> list[Unit]:
        return list(self._session.scalars(select(Unit).order_by(Unit.name)).unique())


class CheckpointRepository(BaseRepository[Checkpoint]):
    model = Checkpoint

    def for_zone(self, zone_id: int) -> list[Checkpoint]:
        return list(self._session.scalars(select(Checkpoint).where(Checkpoint.zone_id == zone_id)).unique())


class DeviceRepository(BaseRepository[Device]):
    model = Device

    def by_code_hash(self, code_hash: str) -> Device | None:
        return self._session.scalar(select(Device).where(Device.code_hash == code_hash))

    def by_token_hash(self, token_hash: str) -> Device | None:
        return self._session.scalar(select(Device).where(Device.token_hash == token_hash))


class AgentRepository(BaseRepository[Agent]):
    model = Agent

    def by_matricule(self, matricule: str) -> Agent | None:
        return self._session.scalar(select(Agent).where(Agent.matricule == matricule))


class AssignmentRepository(BaseRepository[AgentAssignment]):
    model = AgentAssignment

    def open_for_checkpoint(self, checkpoint_id: int) -> AgentAssignment | None:
        return self._session.scalar(select(AgentAssignment).where(
            AgentAssignment.checkpoint_id == checkpoint_id, AgentAssignment.ended_at.is_(None)))

    def used_by(self, *, agent_id: int | None = None, checkpoint_id: int | None = None) -> bool:
        """True when this agent / post appears in the assignment history (it must then be kept)."""
        stmt = select(AgentAssignment.id)
        if agent_id is not None:
            stmt = stmt.where(AgentAssignment.agent_id == agent_id)
        if checkpoint_id is not None:
            stmt = stmt.where(AgentAssignment.checkpoint_id == checkpoint_id)
        return self._session.scalar(stmt.limit(1)) is not None

    def open_for_agent(self, agent_id: int) -> list[AgentAssignment]:
        """Every post the agent currently holds (several when one person keeps entry and exit)."""
        stmt = select(AgentAssignment).where(
            AgentAssignment.agent_id == agent_id, AgentAssignment.ended_at.is_(None)
        ).order_by(AgentAssignment.started_at, AgentAssignment.id)
        return list(self._session.scalars(stmt).unique())

    def history(self, agent_id: int | None, checkpoint_id: int | None,
                limit: int, offset: int) -> list[AgentAssignment]:
        stmt = select(AgentAssignment)
        if agent_id is not None:
            stmt = stmt.where(AgentAssignment.agent_id == agent_id)
        if checkpoint_id is not None:
            stmt = stmt.where(AgentAssignment.checkpoint_id == checkpoint_id)
        stmt = stmt.order_by(AgentAssignment.started_at.desc(), AgentAssignment.id.desc())
        return list(self._session.scalars(stmt.limit(limit).offset(offset)).unique())


class AuthorizationRepository(BaseRepository[ZoneAuthorization]):
    model = ZoneAuthorization

    def for_employee(self, employee_id: int) -> list[ZoneAuthorization]:
        stmt = select(ZoneAuthorization).where(ZoneAuthorization.employee_id == employee_id)
        return list(self._session.scalars(stmt))

    def delete_for_zone(self, zone_id: int) -> int:
        ids = select(ZoneAuthorization.id).where(ZoneAuthorization.zone_id == zone_id)
        self._session.execute(delete(AccessSchedule).where(AccessSchedule.authorization_id.in_(ids)))
        result = self._session.execute(delete(ZoneAuthorization).where(ZoneAuthorization.zone_id == zone_id))
        return result.rowcount or 0

    def find(self, employee_id: int, zone_id: int) -> ZoneAuthorization | None:
        return self._session.scalar(
            select(ZoneAuthorization).where(
                ZoneAuthorization.employee_id == employee_id,
                ZoneAuthorization.zone_id == zone_id,
            )
        )


class PresenceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_locked(self, employee_id: int, zone_id: int) -> ZonePresence | None:
        """Row lock serialises concurrent scans of one person (no-op on SQLite)."""
        stmt = select(ZonePresence).where(
            ZonePresence.employee_id == employee_id, ZonePresence.zone_id == zone_id
        ).with_for_update(of=ZonePresence)
        return self._session.scalar(stmt)

    def inside(self, zone_id: int | None) -> list[ZonePresence]:
        stmt = select(ZonePresence).order_by(ZonePresence.entered_at.desc())
        if zone_id is not None:
            stmt = stmt.where(ZonePresence.zone_id == zone_id)
        return list(self._session.scalars(stmt).unique())

    def add(self, presence: ZonePresence) -> None:
        self._session.add(presence)
        self._session.flush()

    def clear_zone(self, zone_id: int) -> int:
        result = self._session.execute(delete(ZonePresence).where(ZonePresence.zone_id == zone_id))
        return result.rowcount or 0

    def clear_employee(self, employee_id: int) -> int:
        """Forget every 'inside' state of one person (used when the person is archived)."""
        result = self._session.execute(delete(ZonePresence).where(ZonePresence.employee_id == employee_id))
        return result.rowcount or 0

    def remove(self, presence: ZonePresence) -> None:
        self._session.delete(presence)
        self._session.flush()

    def count_by_zone(self, *, department_id: int | None = None, entity_id: int | None = None) -> dict[int, int]:
        """People inside right now, zone by zone (reports), optionally for one department / entity."""
        stmt = select(ZonePresence.zone_id, func.count()).group_by(ZonePresence.zone_id)
        if department_id is not None or entity_id is not None:
            stmt = stmt.join(Employee, Employee.id == ZonePresence.employee_id)
            if department_id is not None:
                stmt = stmt.where(Employee.department_id == department_id)
            if entity_id is not None:
                stmt = stmt.where(Employee.entity_id == entity_id)
        return {row[0]: row[1] for row in self._session.execute(stmt)}  # noqa: C416


class AccessLogRepository(BaseRepository[AccessLog]):
    model = AccessLog

    def last_decisive(self, employee_id: int, zone_id: int) -> AccessLog | None:
        """Latest line that changed the person's situation in a zone: a scan that went
        through (entry or exit) or a console unblock. Refusals are ignored."""
        stmt = (
            select(AccessLog)
            .where(AccessLog.employee_id == employee_id, AccessLog.zone_id == zone_id,
                   (AccessLog.method == ScanMethod.CONSOLE)
                   | AccessLog.verdict.in_([Verdict.AUTHORIZED, Verdict.EXIT_RECORDED]))
            .order_by(AccessLog.occurred_at.desc(), AccessLog.id.desc())
            .limit(1)
        )
        return self._session.scalars(stmt).first()

    def search(self, *, limit: int, offset: int, **filters) -> list[AccessLog]:
        stmt = self._filtered(select(AccessLog), **filters)
        stmt = stmt.order_by(AccessLog.occurred_at.desc()).limit(limit).offset(offset)
        return list(self._session.scalars(stmt).unique())

    def count_matching(self, **filters) -> int:
        ids = self._filtered(select(AccessLog.id), **filters).subquery()
        return self._session.scalar(select(func.count()).select_from(ids)) or 0

    def delete_matching(self, **filters) -> int:
        """Bulk delete of the lines matching the filters (data.purge only)."""
        ids = self._filtered(select(AccessLog.id), **filters)
        result = self._session.execute(delete(AccessLog).where(AccessLog.id.in_(ids)),
                                       execution_options={"synchronize_session": False})
        return result.rowcount or 0

    @staticmethod
    def _filtered(
        stmt,
        *,
        employee_id: int | None = None,
        department_id: int | None = None,
        entity_id: int | None = None,
        zone_id: int | None = None,
        unit_id: int | None = None,
        agent_id: int | None = None,
        checkpoint_id: int | None = None,
        verdict: Verdict | None = None,
        direction: Direction | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        before: datetime | None = None,
        flag: Flag | None = None,
        method: ScanMethod | None = None,
        log_ids: list[int] | None = None,
    ):
        conditions = []
        if log_ids is not None:
            conditions.append(AccessLog.id.in_(log_ids))
        if department_id is not None or entity_id is not None:
            stmt = stmt.join(Employee, Employee.id == AccessLog.employee_id)
            if department_id is not None:
                conditions.append(Employee.department_id == department_id)
            if entity_id is not None:
                conditions.append(Employee.entity_id == entity_id)
        if unit_id is not None:
            stmt = stmt.join(Zone, Zone.id == AccessLog.zone_id)
            conditions.append(Zone.unit_id == unit_id)
        # Conditions are built lazily: comparing a column with None would raise.
        filters = [
            (employee_id, lambda v: AccessLog.employee_id == v),
            (zone_id, lambda v: AccessLog.zone_id == v),
            (agent_id, lambda v: AccessLog.agent_id == v),
            (checkpoint_id, lambda v: AccessLog.checkpoint_id == v),
            (verdict, lambda v: AccessLog.verdict == v),
            (direction, lambda v: AccessLog.direction == v),
            (date_from, lambda v: AccessLog.occurred_at >= v),
            (date_to, lambda v: AccessLog.occurred_at <= v),
            (before, lambda v: AccessLog.occurred_at < v),
            (method, lambda v: AccessLog.method == v),
            # flags is a JSON array (jsonb on PostgreSQL): its text always holds the quoted value.
            (flag, lambda v: cast(AccessLog.flags, String).like(f'%"{v.value}"%')),
        ]
        conditions.extend(build(value) for value, build in filters if value is not None)
        return stmt.where(and_(*conditions)) if conditions else stmt

    def used_by(self, *, zone_id: int | None = None, checkpoint_id: int | None = None,
                device_id: int | None = None, agent_id: int | None = None) -> bool:
        """True when the journal references this item: deleting it would break the history."""
        stmt = select(AccessLog.id)
        for column, value in ((AccessLog.zone_id, zone_id), (AccessLog.checkpoint_id, checkpoint_id),
                              (AccessLog.device_id, device_id), (AccessLog.agent_id, agent_id)):
            if value is not None:
                stmt = stmt.where(column == value)
        return self._session.scalar(stmt.limit(1)) is not None

    def repeat_of(self, badge_id: int, checkpoint_id: int, after: datetime) -> AccessLog | None:
        """The line of the same badge at the same post more recent than ``after`` (repeated scan)."""
        stmt = (select(AccessLog)
                .where(AccessLog.badge_id == badge_id, AccessLog.checkpoint_id == checkpoint_id,
                       AccessLog.occurred_at > after)
                .order_by(AccessLog.occurred_at.desc(), AccessLog.id.desc()).limit(1))
        return self._session.scalars(stmt).first()

    def recent_for_device(self, device_id: int, since: datetime, limit: int) -> list[AccessLog]:
        """A phone's own scans since ``since``, newest first (history shown on the phone)."""
        stmt = (select(AccessLog).where(AccessLog.device_id == device_id, AccessLog.occurred_at >= since)
                .order_by(AccessLog.occurred_at.desc(), AccessLog.id.desc()).limit(limit))
        return list(self._session.scalars(stmt).unique())

    def since(self, start: datetime) -> list[AccessLog]:
        """Journal lines from ``start`` on, oldest first (employee, zone and post loaded with them)."""
        stmt = select(AccessLog).where(AccessLog.occurred_at >= start).order_by(AccessLog.occurred_at, AccessLog.id)
        return list(self._session.scalars(stmt).unique())

    # --- reports (tâche 32): aggregated in SQL, same filters as the journal -------------
    def movements(self, **filters) -> list:
        """Entries, exits, refusals and unblocks per (employee, zone), with first and last passage."""
        stmt = select(
            AccessLog.employee_id, AccessLog.zone_id,
            _count(and_(_SCAN, AccessLog.verdict == Verdict.AUTHORIZED)).label("entries"),
            _count(and_(_SCAN, AccessLog.verdict == Verdict.EXIT_RECORDED)).label("exits"),
            _count(AccessLog.verdict.in_(REFUSED_VERDICTS)).label("refused"),
            _count(AccessLog.method == ScanMethod.CONSOLE).label("unblocks"),
            func.min(AccessLog.occurred_at).label("first_at"),
            func.max(AccessLog.occurred_at).label("last_at"),
        )
        stmt = self._filtered(stmt, **filters).where(AccessLog.employee_id.is_not(None))
        return list(self._session.execute(stmt.group_by(AccessLog.employee_id, AccessLog.zone_id)))

    def zone_activity(self, **filters) -> list:
        """Per zone: entries, exits, refusals and distinct people who entered."""
        entered = and_(_SCAN, AccessLog.verdict == Verdict.AUTHORIZED)
        stmt = select(
            AccessLog.zone_id,
            _count(entered).label("entries"),
            _count(and_(_SCAN, AccessLog.verdict == Verdict.EXIT_RECORDED)).label("exits"),
            _count(AccessLog.verdict.in_(REFUSED_VERDICTS)).label("refused"),
            func.count(func.distinct(case((entered, AccessLog.employee_id)))).label("people"),
        )
        return list(self._session.execute(self._filtered(stmt, **filters).group_by(AccessLog.zone_id)))

    def refusals(self, **filters) -> list:
        """Refused scans (time, verdict, zone, employee), oldest first: the trend is bucketed by local day."""
        stmt = select(AccessLog.occurred_at, AccessLog.verdict, AccessLog.zone_id, AccessLog.employee_id)
        stmt = self._filtered(stmt, **filters).where(AccessLog.verdict.in_(REFUSED_VERDICTS))
        return list(self._session.execute(stmt.order_by(AccessLog.occurred_at)))

    def count_refusals(self, **filters) -> int:
        ids = self._filtered(select(AccessLog.id), **filters).where(AccessLog.verdict.in_(REFUSED_VERDICTS))
        return self._session.scalar(select(func.count()).select_from(ids.subquery())) or 0

    def count_by_verdict(self, since: datetime) -> dict[Verdict, int]:
        stmt = (
            select(AccessLog.verdict, func.count())
            .where(AccessLog.occurred_at >= since)
            .group_by(AccessLog.verdict)
        )
        return {row[0]: row[1] for row in self._session.execute(stmt)}  # noqa: C416



class AuditRepository(BaseRepository[AuditEntry]):
    model = AuditEntry

    def search(self, *, action: str | None = None, date_from: datetime | None = None,
               date_to: datetime | None = None, limit: int = 100, offset: int = 0,
               actor_id: int | None = None, system_only: bool = False,
               target: str | None = None) -> list[AuditEntry]:
        """Newest first."""
        stmt = select(AuditEntry)
        if action:
            stmt = stmt.where(AuditEntry.action.startswith(action))
        if system_only:
            stmt = stmt.where(AuditEntry.actor_id.is_(None))
        elif actor_id is not None:
            stmt = stmt.where(AuditEntry.actor_id == actor_id)
        if target and target.strip():
            stmt = stmt.where(AuditEntry.target.ilike(f"%{_escape_like(target.strip())}%", escape="\\"))
        if date_from is not None:
            stmt = stmt.where(AuditEntry.occurred_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(AuditEntry.occurred_at <= date_to)
        stmt = stmt.order_by(AuditEntry.occurred_at.desc(), AuditEntry.id.desc()).limit(limit).offset(offset)
        return list(self._session.scalars(stmt))


    def actor_ids(self) -> list[int]:
        stmt = select(AuditEntry.actor_id).where(AuditEntry.actor_id.is_not(None)).distinct()
        return list(self._session.scalars(stmt))


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class RoleRepository(BaseRepository[Role]):
    model = Role

    def by_name(self, name: str) -> Role | None:
        return self._session.scalar(select(Role).where(Role.name == name))


class UserRepository(BaseRepository[User]):
    model = User

    def count_by_role(self) -> dict[int, int]:
        """How many accounts hold each role (a role in use cannot be deleted)."""
        stmt = select(User.role_id, func.count()).group_by(User.role_id)
        return {row[0]: row[1] for row in self._session.execute(stmt)}  # noqa: C416

    def by_ids(self, ids: set[int]) -> list[User]:
        return list(self._session.scalars(select(User).where(User.id.in_(ids))))

    def by_username(self, username: str) -> User | None:
        return self._session.scalar(select(User).where(User.username == username))
