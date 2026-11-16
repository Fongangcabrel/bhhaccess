"""Suspicious badge use (SRS FR-90 to FR-93): one row per alert, handled from the console."""
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, JsonType, UtcDateTime
from app.domain.enums import AlertStatus, AlertType
from app.models.employee import Employee
from app.models.zone import Checkpoint


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, index=True)
    type: Mapped[AlertType] = mapped_column(Enum(AlertType, native_enum=False, length=20), index=True)
    status: Mapped[AlertStatus] = mapped_column(Enum(AlertStatus, native_enum=False, length=12),
                                                default=AlertStatus.NEW, index=True)
    badge_id: Mapped[int | None] = mapped_column(ForeignKey("badges.id"), index=True)
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))
    access_log_id: Mapped[int | None] = mapped_column(ForeignKey("access_logs.id", ondelete="SET NULL"))
    checkpoint_id: Mapped[int | None] = mapped_column(ForeignKey("checkpoints.id"))
    message: Mapped[str] = mapped_column(String(300))
    detail: Mapped[dict] = mapped_column(JsonType, default=dict)
    handled_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    handled_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    note: Mapped[str | None] = mapped_column(String(300))

    employee: Mapped[Employee | None] = relationship(lazy="joined")
    checkpoint: Mapped[Checkpoint | None] = relationship(lazy="joined")

    @property
    def employee_name(self) -> str | None:
        return self.employee.full_name if self.employee else None

    @property
    def employee_matricule(self) -> str | None:
        return self.employee.matricule if self.employee else None

    @property
    def checkpoint_name(self) -> str | None:
        return self.checkpoint.name if self.checkpoint else None

    @property
    def zone_name(self) -> str | None:
        return self.checkpoint.zone.name if self.checkpoint else None


class TravelTime(Base):
    """Minimum time to walk from one post to another (both ways). Faster = the badge was copied."""

    __tablename__ = "travel_times"
    __table_args__ = (UniqueConstraint("checkpoint_a_id", "checkpoint_b_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    checkpoint_a_id: Mapped[int] = mapped_column(ForeignKey("checkpoints.id", ondelete="CASCADE"))  # the smaller id
    checkpoint_b_id: Mapped[int] = mapped_column(ForeignKey("checkpoints.id", ondelete="CASCADE"))
    min_seconds: Mapped[int] = mapped_column(Integer)

    checkpoint_a: Mapped[Checkpoint] = relationship(foreign_keys=[checkpoint_a_id], lazy="joined")
    checkpoint_b: Mapped[Checkpoint] = relationship(foreign_keys=[checkpoint_b_id], lazy="joined")

    @property
    def checkpoint_a_name(self) -> str:
        return self.checkpoint_a.name

    @property
    def checkpoint_b_name(self) -> str:
        return self.checkpoint_b.name
