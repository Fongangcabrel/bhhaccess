"""Gate agents (no login) and the history of which post each one stood at."""
from app.core.clock import Clock
from app.core.exceptions import ConflictError, DomainError, NotFoundError
from app.models import Agent, AgentAssignment
from app.repositories.repositories import (
    AccessLogRepository,
    AgentRepository,
    AssignmentRepository,
    CheckpointRepository,
)
from app.services.audit_service import AuditService


class AgentService:
    def __init__(self, agents: AgentRepository, assignments: AssignmentRepository,
                 checkpoints: CheckpointRepository, audit: AuditService, clock: Clock,
                 logs: AccessLogRepository) -> None:
        self._agents = agents
        self._logs = logs
        self._assignments = assignments
        self._checkpoints = checkpoints
        self._audit = audit
        self._clock = clock

    def create(self, actor_id: int, full_name: str, matricule: str | None) -> Agent:
        full_name, matricule = full_name.strip(), (matricule or "").strip() or None
        if not full_name:
            raise DomainError("Nom de l'agent obligatoire")
        if matricule and self._agents.by_matricule(matricule):
            raise ConflictError(f"Matricule déjà utilisé : {matricule}")
        agent = self._agents.add(Agent(full_name=full_name, matricule=matricule))
        self._audit.record(actor_id, "agent.create", full_name)
        return agent

    def update(self, actor_id: int, agent_id: int, full_name: str, matricule: str | None) -> Agent:
        agent = self._require_agent(agent_id)
        full_name, matricule = full_name.strip(), (matricule or "").strip() or None
        if len(full_name) < 2:
            raise DomainError("Nom de l'agent obligatoire")
        if matricule:
            other = self._agents.by_matricule(matricule)
            if other is not None and other.id != agent.id:
                raise ConflictError(f"Matricule déjà utilisé : {matricule}")
        before = {"full_name": agent.full_name, "matricule": agent.matricule}
        agent.full_name, agent.matricule = full_name, matricule
        self._agents.flush()
        self._audit.record(actor_id, "agent.update", full_name, before=before,
                           after={"full_name": full_name, "matricule": matricule})
        return agent

    def delete(self, actor_id: int, agent_id: int) -> None:
        """Only an agent never posted; otherwise deactivate (the journal keeps their name anyway)."""
        agent = self._require_agent(agent_id)
        if self._assignments.used_by(agent_id=agent.id) or self._logs.used_by(agent_id=agent.id):
            raise ConflictError("Cet agent a déjà été posté : désactivez-le plutôt pour garder l'historique")
        self._agents.remove(agent)
        self._audit.record(actor_id, "agent.delete", agent.full_name)

    def set_active(self, actor_id: int, agent_id: int, active: bool) -> Agent:
        agent = self._require_agent(agent_id)
        agent.is_active = active
        if not active:
            for assignment in self._assignments.open_for_agent(agent_id):
                self._close(assignment)
        self._audit.record(actor_id, "agent.active", agent.full_name,
                           before={"active": not active}, after={"active": active})
        return agent

    def all(self) -> list[Agent]:
        return self._agents.list(limit=1000)

    def current_posts(self, agent_id: int) -> list[AgentAssignment]:
        return self._assignments.open_for_agent(agent_id)

    def assign(self, actor_id: int, checkpoint_id: int, agent_id: int | None,
               keep_other_posts: bool = False) -> AgentAssignment | None:
        """Put ``agent_id`` at the post (or empty the post when None).

        A post has at most one agent. An agent normally *moves* (rotation: the previous post is
        closed, the history keeps it). With ``keep_other_posts`` the agent holds this post as
        well, e.g. the entry and the exit of a zone that has a single door.
        """
        checkpoint = self._checkpoints.get(checkpoint_id)
        if checkpoint is None:
            raise NotFoundError("Point de contrôle introuvable")
        if agent_id is not None and not checkpoint.usable:
            raise DomainError("Ce poste est désactivé")
        current = self._assignments.open_for_checkpoint(checkpoint_id)
        if agent_id is None:
            self._close(current)
            self._audit.record(actor_id, "agent.unassign", checkpoint.name)
            return None
        agent = self._require_agent(agent_id)
        if not agent.is_active:
            raise DomainError("Cet agent est désactivé")
        if current is not None and current.agent_id == agent_id:
            return current
        self._close(current)  # the agent who was there leaves this post
        left = []
        if not keep_other_posts:
            for previous in self._assignments.open_for_agent(agent_id):
                left.append(previous.checkpoint_name)
                self._close(previous)
        assignment = self._assignments.add(AgentAssignment(
            agent_id=agent_id, checkpoint_id=checkpoint_id, started_at=self._clock.now()))
        self._audit.record(actor_id, "agent.assign", agent.full_name, checkpoint=checkpoint.name,
                           also_keeps=[a.checkpoint_name for a in self._assignments.open_for_agent(agent_id)
                                       if a.checkpoint_id != checkpoint_id],
                           left=left, replaced=current.agent_name if current else None)
        return assignment

    def history(self, agent_id: int | None, checkpoint_id: int | None,
                limit: int = 100, offset: int = 0) -> list[AgentAssignment]:
        return self._assignments.history(agent_id, checkpoint_id, limit, offset)

    def _close(self, assignment: AgentAssignment | None) -> None:
        if assignment is not None:
            assignment.ended_at = self._clock.now()
            self._assignments.flush()

    def _require_agent(self, agent_id: int) -> Agent:
        agent = self._agents.get(agent_id)
        if agent is None:
            raise NotFoundError("Agent introuvable")
        return agent
