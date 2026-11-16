from datetime import datetime

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, JsonType, UtcDateTime
from app.domain.enums import Direction, ScanMethod, Verdict
from app.models.device import Device
from app.models.employee import Employee
from app.models.zone import Checkpoint, Zone


class AccessLog(Base):
    """Immutable scan journal. Lines are never edited, only purged (data.purge)."""

    __tablename__ = "access_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(UtcDateTime, index=True)
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), index=True)
    badge_id: Mapped[int | None] = mapped_column(ForeignKey("badges.id"))
    zone_id: Mapped[int] = mapped_column(ForeignKey("zones.id"), index=True)
    checkpoint_id: Mapped[int] = mapped_column(ForeignKey("checkpoints.id"), index=True)
    direction: Mapped[Direction] = mapped_column(Enum(Direction, native_enum=False))
    verdict: Mapped[Verdict] = mapped_column(Enum(Verdict, native_enum=False), index=True)
    flags: Mapped[list] = mapped_column(JsonType, default=list)
    operator_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))  # back-office user (manual unblock...)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id"))
    agent_id: Mapped[int | None] = mapped_column(ForeignKey("agents.id"), index=True)
    agent_name: Mapped[str | None] = mapped_column(String(160))  # snapshot: survives agent renames/deletion
    reason: Mapped[str | None] = mapped_column(String(500))
    method: Mapped[ScanMethod] = mapped_column(Enum(ScanMethod, native_enum=False, length=10),
                                               default=ScanMethod.QR)

    employee: Mapped["Employee | None"] = relationship(lazy="joined")
    zone: Mapped["Zone"] = relationship(lazy="joined")
    checkpoint: Mapped["Checkpoint"] = relationship(lazy="joined")
    device: Mapped["Device | None"] = relationship(lazy="joined")

    @property
    def employee_name(self) -> str | None:
        return self.employee.full_name if self.employee else None

    @property
    def employee_matricule(self) -> str | None:
        return self.employee.matricule if self.employee else None

    @property
    def zone_name(self) -> str:
        return self.zone.name

    @property
    def checkpoint_name(self) -> str:
        return self.checkpoint.name

    @property
    def unit_id(self) -> int:
        return self.zone.unit_id

    @property
    def unit_name(self) -> str:
        return self.zone.unit.name

    @property
    def device_name(self) -> str | None:
        return self.device.name if self.device else None


class AuditEntry(Base):
    """Administrative trace (who changed what). Never deletable."""

    __tablename__ = "audit_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(UtcDateTime, index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    target: Mapped[str | None] = mapped_column(String(120))
    detail: Mapped[dict] = mapped_column(JsonType, default=dict)
    ip: Mapped[str | None] = mapped_column(String(45))
