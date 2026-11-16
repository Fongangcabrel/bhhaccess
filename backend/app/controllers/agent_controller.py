from fastapi import APIRouter, Depends, Query, Response, status

from app.controllers.deps import get_agent_service, require
from app.domain.permissions import Permission
from app.models import Agent, User
from app.schemas.dto import ActiveIn, AgentIn, AgentOut, AgentPostOut, AssignIn, AssignmentOut
from app.services.agent_service import AgentService

router = APIRouter(tags=["agents"])


def _view(agent: Agent, service: AgentService) -> AgentOut:
    out = AgentOut.model_validate(agent)
    out.posts = [
        AgentPostOut(checkpoint_id=a.checkpoint_id, checkpoint_name=a.checkpoint_name,
                     direction=a.checkpoint.direction, zone_name=a.zone_name, unit_name=a.unit_name,
                     since=a.started_at)
        for a in service.current_posts(agent.id)
    ]
    if out.posts:
        first = out.posts[0]
        out.checkpoint_id, out.checkpoint_name = first.checkpoint_id, first.checkpoint_name
        out.zone_name, out.unit_name = first.zone_name, first.unit_name
    return out


@router.get("/agents", response_model=list[AgentOut])
def list_agents(_: User = Depends(require(Permission.ZONES_VIEW)),
                service: AgentService = Depends(get_agent_service)):
    return [_view(a, service) for a in service.all()]


@router.post("/agents", response_model=AgentOut, status_code=status.HTTP_201_CREATED)
def create_agent(body: AgentIn, actor: User = Depends(require(Permission.ZONES_MANAGE)),
                 service: AgentService = Depends(get_agent_service)):
    return _view(service.create(actor.id, body.full_name, body.matricule), service)


@router.patch("/agents/{agent_id}", response_model=AgentOut)
def update_agent(agent_id: int, body: AgentIn, actor: User = Depends(require(Permission.ZONES_MANAGE)),
                 service: AgentService = Depends(get_agent_service)):
    return _view(service.update(actor.id, agent_id, body.full_name, body.matricule), service)


@router.delete("/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent(agent_id: int, actor: User = Depends(require(Permission.ZONES_MANAGE)),
                 service: AgentService = Depends(get_agent_service)):
    service.delete(actor.id, agent_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/agents/{agent_id}/active", response_model=AgentOut)
def set_agent_active(agent_id: int, body: ActiveIn, actor: User = Depends(require(Permission.ZONES_MANAGE)),
                     service: AgentService = Depends(get_agent_service)):
    return _view(service.set_active(actor.id, agent_id, body.is_active), service)


@router.put("/checkpoints/{checkpoint_id}/agent", status_code=status.HTTP_204_NO_CONTENT)
def assign_agent(checkpoint_id: int, body: AssignIn, actor: User = Depends(require(Permission.ZONES_MANAGE)),
                 service: AgentService = Depends(get_agent_service)) -> None:
    service.assign(actor.id, checkpoint_id, body.agent_id, body.keep_other_posts)


@router.get("/assignments", response_model=list[AssignmentOut])
def assignment_history(agent_id: int | None = None, checkpoint_id: int | None = None,
                       limit: int = Query(100, le=500), offset: int = 0,
                       _: User = Depends(require(Permission.LOGS_VIEW)),
                       service: AgentService = Depends(get_agent_service)):
    return service.history(agent_id, checkpoint_id, limit, offset)
