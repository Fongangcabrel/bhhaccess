"""First-start seeding: default roles and the initial super admin."""
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import hash_password
from app.domain.permissions import DEFAULT_ROLES
from app.models import Role, User
from app.repositories.repositories import RoleRepository, UserRepository


def seed_defaults(session: Session, settings: Settings) -> None:
    roles, users = RoleRepository(session), UserRepository(session)
    for name, spec in DEFAULT_ROLES.items():
        if roles.by_name(name) is None:
            roles.add(Role(name=name, label=spec["label"],
                           permissions=sorted(p.value for p in spec["permissions"])))
    if users.by_username(settings.initial_admin_username) is None:
        users.add(User(
            username=settings.initial_admin_username, full_name="Super admin",
            password_hash=hash_password(settings.initial_admin_password),
            must_change_password=settings.initial_admin_must_change_password,
            role_id=roles.by_name("super_admin").id,
        ))
    session.commit()
