from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, UtcDateTime


class Device(Base):
    """A phone paired once with a one-time code; afterwards it scans without any login.

    Only SHA-256 hashes of the pairing code and of the device token are stored.
    """

    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    code_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    code_expires_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    token_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)
    paired_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    last_seen_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    # The phone says the result aloud (« Entrée autorisée, Jean Mbarga »); the beep always stays.
    voice_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    # What the phone covers; empty = the whole site (phones paired before this setting existed).
    scope: Mapped[list["DeviceScope"]] = relationship(cascade="all, delete-orphan", lazy="selectin",
                                                      order_by="DeviceScope.id")

    def covers(self, checkpoint) -> bool:
        """No perimeter set: the whole site. Otherwise the post, its zone or its unit is listed."""
        return not self.scope or any(item.covers(checkpoint) for item in self.scope)

    @property
    def scope_summary(self) -> str:
        return " · ".join(item.label for item in self.scope) if self.scope else "Tout le site"

    @property
    def scope_ids(self) -> dict:
        return {"unit_ids": [s.unit_id for s in self.scope if s.unit_id is not None],
                "zone_ids": [s.zone_id for s in self.scope if s.zone_id is not None],
                "checkpoint_ids": [s.checkpoint_id for s in self.scope if s.checkpoint_id is not None]}

    @property
    def status(self) -> str:
        if self.revoked_at is not None:
            return "REVOQUE"
        return "APPAIRE" if self.token_hash else "EN_ATTENTE"


class DeviceScope(Base):
    """One item of a phone's perimeter: a whole unit, a whole zone, or one post.

    A unit or a zone also covers the posts created there later.
    """

    __tablename__ = "device_scopes"
    __table_args__ = (
        CheckConstraint("(CASE WHEN unit_id IS NULL THEN 0 ELSE 1 END) + (CASE WHEN zone_id IS NULL THEN 0 ELSE 1 END)"
                        " + (CASE WHEN checkpoint_id IS NULL THEN 0 ELSE 1 END) = 1",
                        name="ck_device_scopes_one_target"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    unit_id: Mapped[int | None] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"))
    zone_id: Mapped[int | None] = mapped_column(ForeignKey("zones.id", ondelete="CASCADE"))
    checkpoint_id: Mapped[int | None] = mapped_column(ForeignKey("checkpoints.id", ondelete="CASCADE"))

    unit: Mapped["Unit | None"] = relationship(lazy="joined")  # noqa: F821  (names resolved by the registry)
    zone: Mapped["Zone | None"] = relationship(lazy="joined")  # noqa: F821
    checkpoint: Mapped["Checkpoint | None"] = relationship(lazy="joined")  # noqa: F821

    def covers(self, checkpoint) -> bool:
        return (self.checkpoint_id == checkpoint.id or self.zone_id == checkpoint.zone_id
                or (self.unit_id is not None and self.unit_id == checkpoint.zone.unit_id))

    @property
    def label(self) -> str:
        if self.unit is not None:
            return f"{self.unit.name} (toute l'unité)"
        if self.zone is not None:
            return f"{self.zone.name} (toute la zone)"
        return f"{self.checkpoint.name} · {self.checkpoint.zone.name}" if self.checkpoint else "?"
