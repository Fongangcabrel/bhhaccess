"""Generic repository: the only place that talks SQL for a given aggregate."""
from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import Base

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    model: type[T]

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, entity_id: int) -> T | None:
        return self._session.get(self.model, entity_id)

    def add(self, entity: T) -> T:
        self._session.add(entity)
        self._session.flush()  # assigns the primary key without committing
        return entity

    def flush(self) -> None:
        self._session.flush()

    def refresh(self, entity: T) -> None:
        self._session.refresh(entity)

    def remove(self, entity: T) -> None:
        self._session.delete(entity)
        self._session.flush()

    def list(self, limit: int = 100, offset: int = 0) -> list[T]:
        stmt = select(self.model).order_by(self.model.id).limit(limit).offset(offset)  # type: ignore[attr-defined]
        return list(self._session.scalars(stmt))
