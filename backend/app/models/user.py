from datetime import datetime

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, JsonType, UtcDateTime
from app.domain.enums import OverrideEffect


class Role(Base):
    """Permission template. ``permissions`` is a list of Permission values."""

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    label: Mapped[str] = mapped_column(String(120))
    permissions: Mapped[list] = mapped_column(JsonType, default=list)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(String(255))
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    is_active: Mapped[bool] = mapped_column(default=True)
    # Temporary password (new account, reset by an admin): every other action is refused until changed.
    must_change_password: Mapped[bool] = mapped_column(default=False)
    # Sessions opened before this moment are refused (password changed or reset).
    password_changed_at: Mapped[datetime | None] = mapped_column(UtcDateTime)

    role: Mapped[Role] = relationship()
    overrides: Mapped[list["UserPermissionOverride"]] = relationship(
        cascade="all, delete-orphan"
    )


class UserPermissionOverride(Base):
    """Per-person exception to the role bundle: grant or take away one action."""

    __tablename__ = "user_permission_overrides"
    __table_args__ = (UniqueConstraint("user_id", "permission"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    permission: Mapped[str] = mapped_column(String(60))
    effect: Mapped[OverrideEffect] = mapped_column(Enum(OverrideEffect, native_enum=False))
