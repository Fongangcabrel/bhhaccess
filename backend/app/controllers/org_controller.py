"""Entities and departments (console « Organisation »). Reading: employees.view; changes: employees.edit."""
from fastapi import APIRouter, Depends, status

from app.controllers.deps import get_org_service, require
from app.domain.permissions import Permission
from app.models import User
from app.schemas.dto import DepartmentOut, EntityOut, NameIn, OrgOut
from app.services.org_service import OrgService

router = APIRouter(prefix="/org", tags=["organisation"])
EDIT = Permission.EMPLOYEES_EDIT


@router.get("", response_model=OrgOut)
def org_tree(_: User = Depends(require(Permission.EMPLOYEES_VIEW)), service: OrgService = Depends(get_org_service)):
    """The two lists, with the number of employees using each item."""
    return service.tree()


@router.post("/entities", response_model=EntityOut, status_code=status.HTTP_201_CREATED)
def create_entity(body: NameIn, actor: User = Depends(require(EDIT)), service: OrgService = Depends(get_org_service)):
    return service.create_entity(actor.id, body.name)


@router.patch("/entities/{entity_id}", response_model=EntityOut)
def rename_entity(entity_id: int, body: NameIn, actor: User = Depends(require(EDIT)),
                  service: OrgService = Depends(get_org_service)):
    return service.rename_entity(actor.id, entity_id, body.name)


@router.delete("/entities/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entity(entity_id: int, actor: User = Depends(require(EDIT)), service: OrgService = Depends(get_org_service)):
    service.delete_entity(actor.id, entity_id)


@router.post("/departments", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
def create_department(body: NameIn, actor: User = Depends(require(EDIT)),
                      service: OrgService = Depends(get_org_service)):
    return service.create_department(actor.id, body.name)


@router.patch("/departments/{department_id}", response_model=DepartmentOut)
def rename_department(department_id: int, body: NameIn, actor: User = Depends(require(EDIT)),
                      service: OrgService = Depends(get_org_service)):
    return service.rename_department(actor.id, department_id, body.name)


@router.delete("/departments/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(department_id: int, actor: User = Depends(require(EDIT)),
                      service: OrgService = Depends(get_org_service)):
    service.delete_department(actor.id, department_id)
