from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, UtcDateTime
from app.models.zone import Checkpoint


class Agent(Base):
    """A gate agent. Agents never log in: they are only recorded for the reporting."""

    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(160))
    matricule: Mapped[str | None] = mapped_column(String(40), unique=True)
    is_active: Mapped[bool] = mapped_column(default=True)


class AgentAssignment(Base):
    """History of who stood at which post: open while ``ended_at`` is NULL."""

    __tablename__ = "agent_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), index=True)
    checkpoint_id: Mapped[int] = mapped_column(ForeignKey("checkpoints.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(UtcDateTime, index=True)
    ended_at: Mapped[datetime | None] = mapped_column(UtcDateTime)

    agent: Mapped[Agent] = relationship(lazy="joined")
    checkpoint: Mapped[Checkpoint] = relationship(lazy="joined", overlaps="current_assignment")

    @property
    def agent_name(self) -> str:
        return self.agent.full_name

    @property
    def checkpoint_name(self) -> str:
        return self.checkpoint.name

    @property
    def zone_name(self) -> str:
        return self.checkpoint.zone.name

    @property
    def unit_name(self) -> str:
        return self.checkpoint.zone.unit.name
