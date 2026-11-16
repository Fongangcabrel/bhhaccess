"""Entities (companies of the BHH group) and departments: two separate lists, managed from the console.

An employee picks one of each, independently. Nothing that an employee references is deleted:
rename it, or move the people first (the journal and the exports show these names).
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, DomainError, NotFoundError
from app.models import Department, Employee, Entity
from app.repositories.repositories import DepartmentRepository, EntityRepository
from app.services.audit_service import AuditService


def _clean(name: str) -> str:
    name = " ".join((name or "").split())
    if not name:
        raise DomainError("Le nom est obligatoire")
    return name


class OrgService:
    def __init__(self, session: Session, audit: AuditService) -> None:
        self._session = session
        self._entities = EntityRepository(session)
        self._departments = DepartmentRepository(session)
        self._audit = audit

    # --- reading -----------------------------------------------------------
    def tree(self) -> dict:
        """Both lists, each item with the number of employees using it (archived included)."""
        by_entity = dict(self._session.execute(
            select(Employee.entity_id, func.count()).where(Employee.entity_id.is_not(None)).group_by(Employee.entity_id)
        ).all())
        by_department = dict(self._session.execute(
            select(Employee.department_id, func.count()).where(Employee.department_id.is_not(None))
            .group_by(Employee.department_id)
        ).all())

        def items(rows, counts):
            return [{"id": x.id, "name": x.name, "employees": counts.get(x.id, 0)}
                    for x in sorted(rows, key=lambda x: x.name.lower())]

        return {"entities": items(self._entities.list(limit=10_000), by_entity),
                "departments": items(self._departments.list(limit=10_000), by_department)}

    # --- entities ----------------------------------------------------------
    def create_entity(self, actor_id: int, name: str) -> Entity:
        name = _clean(name)
        if self._entity_named(name):
            raise ConflictError(f"Entité déjà existante : {name}")
        entity = self._entities.add(Entity(name=name))
        self._audit.record(actor_id, "entity.create", name)
        return entity

    def rename_entity(self, actor_id: int, entity_id: int, name: str) -> Entity:
        entity, name = self._entity(entity_id), _clean(name)
        other = self._entity_named(name)
        if other is not None and other.id != entity.id:
            raise ConflictError(f"Entité déjà existante : {name}")
        old, entity.name = entity.name, name
        self._entities.flush()
        if old != name:
            self._audit.record(actor_id, "entity.rename", name, before={"name": old}, after={"name": name})
        return entity

    def delete_entity(self, actor_id: int, entity_id: int) -> None:
        entity = self._entity(entity_id)
        if self._count(Employee.entity_id == entity.id):
            raise ConflictError("Des employés appartiennent à cette entité : changez-les d'entité ou renommez-la")
        self._entities.remove(entity)
        self._audit.record(actor_id, "entity.delete", entity.name)

    # --- departments -------------------------------------------------------
    def create_department(self, actor_id: int, name: str) -> Department:
        name = _clean(name)
        if self._departments.by_name(name):
            raise ConflictError(f"Département déjà existant : {name}")
        department = self._departments.add(Department(name=name))
        self._audit.record(actor_id, "department.create", name)
        return department

    def rename_department(self, actor_id: int, department_id: int, name: str) -> Department:
        department, name = self._department(department_id), _clean(name)
        other = self._departments.by_name(name)
        if other is not None and other.id != department.id:
            raise ConflictError(f"Département déjà existant : {name}")
        old, department.name = department.name, name
        self._departments.flush()
        if old != name:
            self._audit.record(actor_id, "department.rename", name, before={"name": old}, after={"name": name})
        return department

    def delete_department(self, actor_id: int, department_id: int) -> None:
        department = self._department(department_id)
        if self._count(Employee.department_id == department.id):
            raise ConflictError("Des employés sont dans ce département : changez-les de département ou renommez-le")
        self._departments.remove(department)
        self._audit.record(actor_id, "department.delete", department.name)

    # --- employee form ----------------------------------------------------------
    def check_assignment(self, entity_id: int | None, department_id: int | None) -> None:
        """The chosen entity and department must exist (they are independent of each other)."""
        if entity_id is not None:
            self._entity(entity_id)
        if department_id is not None:
            self._department(department_id)

    # --- internals ---------------------------------------------------------
    def _entity(self, entity_id: int) -> Entity:
        entity = self._entities.get(entity_id)
        if entity is None:
            raise NotFoundError("Entité introuvable")
        return entity

    def _department(self, department_id: int) -> Department:
        department = self._departments.get(department_id)
        if department is None:
            raise NotFoundError("Département introuvable")
        return department

    def _entity_named(self, name: str) -> Entity | None:
        return self._session.scalar(select(Entity).where(func.lower(Entity.name) == name.lower()))

    def _count(self, condition) -> int:
        return self._session.scalar(select(func.count()).select_from(Employee).where(condition)) or 0
