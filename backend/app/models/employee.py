from datetime import datetime

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, JsonType, UtcDateTime
from app.domain.enums import EmployeeStatus
from app.models.organization import Department, Entity


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)
    matricule: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    last_name: Mapped[str] = mapped_column(String(120))
    first_name: Mapped[str] = mapped_column(String(120))
    job_title: Mapped[str | None] = mapped_column(String(120))
    entity_id: Mapped[int | None] = mapped_column(ForeignKey("entities.id"))
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"))
    extra: Mapped[dict] = mapped_column(JsonType, default=dict)
    status: Mapped[EmployeeStatus] = mapped_column(
        Enum(EmployeeStatus, native_enum=False), default=EmployeeStatus.ACTIVE
    )
    photo_path: Mapped[str | None] = mapped_column(String(255))  # file name in the photos volume
    # Filled while the employee is archived (cleared on restore; the audit keeps the history).
    archived_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    archived_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    archive_reason: Mapped[str | None] = mapped_column(String(500))

    entity: Mapped[Entity | None] = relationship()
    department: Mapped[Department | None] = relationship()

    @property
    def has_photo(self) -> bool:
        return self.photo_path is not None

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def entity_name(self) -> str | None:
        return self.entity.name if self.entity else None

    @property
    def department_name(self) -> str | None:
        return self.department.name if self.department else None
