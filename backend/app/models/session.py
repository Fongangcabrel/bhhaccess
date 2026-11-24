"""Back-office sessions (FR-01): refresh tokens and system settings."""
from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, JsonType, UtcDateTime


class RefreshToken(Base):
    """One refresh token of a session. Only its SHA-256 is stored.

    A token is used once: each refresh revokes it and issues the next one of the same family
    (the session). A revoked token presented again means it was copied: the whole family stops.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    family: Mapped[str] = mapped_column(String(32), index=True)  # one login = one family
    started_at: Mapped[datetime] = mapped_column(UtcDateTime)  # login time of the session
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime)  # end of the session, kept by every rotation
    revoked_at: Mapped[datetime | None] = mapped_column(UtcDateTime)


class AppSetting(Base):
    """A system setting changed in the console (system.config); absent = the installation default."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[object] = mapped_column(JsonType)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
