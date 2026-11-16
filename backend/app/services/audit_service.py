"""Append-only administrative trace (SRS FR-71, FR-72): who, when, from where, before / after."""
from dataclasses import dataclass
from datetime import datetime

from app.core.clock import Clock
from app.models import AuditEntry
from app.repositories.repositories import AuditRepository, UserRepository

SYSTEM_ACTOR = "Téléphone / système"


@dataclass(frozen=True)
class AuditFilters:
    action: str | None = None  # prefix: "badge" matches badge.issue and badge.revoke
    actor_id: int | None = None
    system_only: bool = False  # actions without a signed-in author (phone pairing...)
    target: str | None = None  # contains, case-insensitive
    date_from: datetime | None = None
    date_to: datetime | None = None


class AuditService:
    """Exposes no update or delete."""

    def __init__(self, repo: AuditRepository, clock: Clock, ip: str | None = None,
                 users: UserRepository | None = None) -> None:
        self._repo = repo
        self._clock = clock
        self._ip = ip
        self._users = users

    def record(self, actor_id: int | None, action: str, target: str | None = None, **detail) -> None:
        self._repo.add(
            AuditEntry(
                occurred_at=self._clock.now(), actor_id=actor_id,
                action=action, target=target, detail=detail, ip=self._ip,
            )
        )

    def search(self, filters: AuditFilters, limit: int = 100, offset: int = 0) -> list[AuditEntry]:
        """Newest first; each entry gets an ``actor_name`` for display and exports."""
        entries = self._repo.search(
            action=filters.action, actor_id=filters.actor_id, system_only=filters.system_only,
            target=filters.target, date_from=filters.date_from, date_to=filters.date_to,
            limit=limit, offset=offset,
        )
        names = self._names({e.actor_id for e in entries if e.actor_id is not None})
        for entry in entries:
            entry.actor_name = names.get(entry.actor_id, SYSTEM_ACTOR) if entry.actor_id else SYSTEM_ACTOR
        return entries

    def actors(self) -> list[dict]:
        """People who appear in the audit, for the author filter (works without users.manage)."""
        names = self._names(set(self._repo.actor_ids()))
        return sorted(({"id": i, "name": n} for i, n in names.items()), key=lambda a: a["name"].lower())

    def list(self, limit: int = 100, offset: int = 0) -> list[AuditEntry]:
        return self.search(AuditFilters(), limit, offset)

    def _names(self, ids: set[int]) -> dict[int, str]:
        if not ids or self._users is None:
            return {}
        return {u.id: u.full_name for u in self._users.by_ids(ids)}
