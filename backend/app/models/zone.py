from datetime import datetime, time
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, JsonType, UtcDateTime
from app.domain.access_window import Slot
from app.domain.enums import AntiPassbackMode, Direction, ZoneSensitivity
from app.models.employee import Employee

if TYPE_CHECKING:
    from app.models.agent import AgentAssignment


class Unit(Base):
    """A site/building/service that groups zones (the level used to configure access)."""

    __tablename__ = "units"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)

    zones: Mapped[list["Zone"]] = relationship(back_populates="unit", order_by="Zone.name")


class Zone(Base):
    __tablename__ = "zones"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    code: Mapped[str | None] = mapped_column(String(20), unique=True)  # short code, e.g. DC-01
    description: Mapped[str | None] = mapped_column(String(500))
    sensitivity: Mapped[ZoneSensitivity] = mapped_column(
        Enum(ZoneSensitivity, native_enum=False), default=ZoneSensitivity.STANDARD
    )
    is_active: Mapped[bool] = mapped_column(default=True)  # inactive: its posts cannot scan
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"), index=True)
    antipassback_mode: Mapped[AntiPassbackMode] = mapped_column(
        Enum(AntiPassbackMode, native_enum=False), default=AntiPassbackMode.DISABLED
    )
    # « Signalé » mode: also show the agent a "double entrée" warning (FR-82, Backend Schema).
    antipassback_warn_agent: Mapped[bool] = mapped_column(default=False)

    unit: Mapped[Unit] = relationship(back_populates="zones", lazy="joined")

    @property
    def unit_name(self) -> str:
        return self.unit.name


class Checkpoint(Base):
    """A physical scan point (a gate) bound to one zone and one direction."""

    __tablename__ = "checkpoints"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    zone_id: Mapped[int] = mapped_column(ForeignKey("zones.id"))
    direction: Mapped[Direction] = mapped_column(Enum(Direction, native_enum=False))
    is_active: Mapped[bool] = mapped_column(default=True)

    zone: Mapped[Zone] = relationship(lazy="joined")
    # The agent currently posted here (None when nobody is assigned).
    current_assignment: Mapped["AgentAssignment | None"] = relationship(
        "AgentAssignment",
        primaryjoin="and_(AgentAssignment.checkpoint_id == Checkpoint.id, AgentAssignment.ended_at.is_(None))",
        viewonly=True, uselist=False, lazy="selectin",
    )

    @property
    def zone_name(self) -> str:
        return self.zone.name

    @property
    def unit_id(self) -> int:
        return self.zone.unit_id

    @property
    def unit_name(self) -> str:
        return self.zone.unit.name

    @property
    def usable(self) -> bool:
        """A post can scan only when it and its zone are both active."""
        return self.is_active and self.zone.is_active

    @property
    def agent_id(self) -> int | None:
        return self.current_assignment.agent_id if self.current_assignment else None

    @property
    def agent_name(self) -> str | None:
        return self.current_assignment.agent.full_name if self.current_assignment else None


class ZoneAuthorization(Base):
    __tablename__ = "zone_authorizations"
    __table_args__ = (UniqueConstraint("employee_id", "zone_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    zone_id: Mapped[int] = mapped_column(ForeignKey("zones.id"))
    valid_from: Mapped[datetime | None] = mapped_column(UtcDateTime)  # None: valid at once
    valid_until: Mapped[datetime | None] = mapped_column(UtcDateTime)  # None: no end (temporary access otherwise)
    granted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    # Weekly time slots; none means 24 h / 24 (SRS FR-43).
    schedules: Mapped[list["AccessSchedule"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="AccessSchedule.id")

    @property
    def slots(self) -> list[Slot]:
        return [s.slot for s in self.schedules]


class AccessSchedule(Base):
    """One allowed slot of an authorisation: days of the week + hours (Backend Schema)."""

    __tablename__ = "access_schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    authorization_id: Mapped[int] = mapped_column(
        ForeignKey("zone_authorizations.id", ondelete="CASCADE"), index=True)
    weekdays: Mapped[list] = mapped_column(JsonType)  # [1..7], 1 = Monday
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)

    @property
    def slot(self) -> Slot:
        return Slot(tuple(self.weekdays), self.start_time, self.end_time)


class ZonePresence(Base):
    """Who is currently inside a soft/strict anti-passback zone."""

    __tablename__ = "zone_presence"

    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), primary_key=True)
    zone_id: Mapped[int] = mapped_column(ForeignKey("zones.id"), primary_key=True)
    entered_at: Mapped[datetime] = mapped_column(UtcDateTime)
    checkpoint_id: Mapped[int | None] = mapped_column(ForeignKey("checkpoints.id"))

    employee: Mapped[Employee] = relationship(lazy="joined")
    zone: Mapped[Zone] = relationship(lazy="joined")
