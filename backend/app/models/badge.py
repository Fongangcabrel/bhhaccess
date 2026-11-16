from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, UtcDateTime
from app.domain.enums import BadgeStatus, RevocationReason


class Badge(Base):
    """A permanent QR badge. ``version`` is bumped on re-issue, killing the old QR."""

    __tablename__ = "badges"
    __table_args__ = (
        # One active badge per employee, enforced by the database (SRS FR-51): two concurrent
        # issues cannot both succeed. Non-native enums store the member NAME.
        Index("one_active_badge", "employee_id", unique=True,
              postgresql_where=text("status = 'ACTIVE'"), sqlite_where=text("status = 'ACTIVE'")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    version: Mapped[int] = mapped_column(default=1)
    status: Mapped[BadgeStatus] = mapped_column(
        Enum(BadgeStatus, native_enum=False), default=BadgeStatus.ACTIVE
    )
    issued_at: Mapped[datetime] = mapped_column(UtcDateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    revoked_reason: Mapped[RevocationReason | None] = mapped_column(
        Enum(RevocationReason, native_enum=False, length=20)
    )
    revoked_note: Mapped[str | None] = mapped_column(String(300))
    revoked_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
