import os
from datetime import UTC, datetime, timedelta

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import Settings
from app.core.database import Base, build_engine
from app.core.security import hash_password
from app.main import create_app
from app.models import Role, User


class FakeClock:
    def __init__(self) -> None:
        self.current = datetime(2026, 11, 11, 8, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self.current

    def advance(self, **kwargs) -> None:
        self.current += timedelta(**kwargs)


# Set BHH_TEST_DATABASE_URL to run the very same suite on a real PostgreSQL.
TEST_DB_URL = os.environ.get("BHH_TEST_DATABASE_URL", "sqlite://")


@pytest.fixture(scope="session", autouse=True)
def _migrated_database():
    """On PostgreSQL the schema comes from the Alembic migrations, exactly as in production."""
    if TEST_DB_URL.startswith("sqlite"):
        yield
        return
    os.environ["BHH_DATABASE_URL"] = TEST_DB_URL
    config = Config("alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    yield


@pytest.fixture(autouse=True)
def _clean_tables(_migrated_database):
    if not TEST_DB_URL.startswith("sqlite"):
        engine = build_engine(TEST_DB_URL)
        names = ", ".join(t.name for t in Base.metadata.sorted_tables)
        with engine.begin() as connection:
            connection.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
        engine.dispose()
    yield


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def app(clock, tmp_path):
    settings = Settings(database_url=TEST_DB_URL, jwt_secret="test-secret-test-secret-test-secret-0123",
                        initial_admin_username="admin", initial_admin_password="pw-admin",
                        initial_admin_must_change_password=False,
                        photos_dir=str(tmp_path / "photos"))
    return create_app(settings, clock)


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)


def _login(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def admin(client):
    return _login(client, "admin", "pw-admin")


@pytest.fixture
def make_user(app, client):
    """Create a user with a given default role and return its auth headers."""

    def factory(username: str, role_name: str) -> dict[str, str]:
        with app.state.session_factory() as session:
            role = session.query(Role).filter_by(name=role_name).one()
            session.add(User(username=username, full_name=username,
                             password_hash=hash_password("pw"), role_id=role.id))
            session.commit()
        return _login(client, username, "pw")

    return factory


@pytest.fixture
def agent(make_user):
    return make_user("agent1", "agent")


@pytest.fixture
def world(client, admin):
    """A strict zone with an entry and an exit gate, one authorised employee with a badge."""
    zone = client.post("/api/zones", headers=admin,
                       json={"name": "Usine", "antipassback_mode": "STRICT"}).json()
    entry = client.post(f"/api/zones/{zone['id']}/checkpoints", headers=admin,
                        json={"name": "Entrée usine", "direction": "ENTREE"}).json()
    exit_ = client.post(f"/api/zones/{zone['id']}/checkpoints", headers=admin,
                        json={"name": "Sortie usine", "direction": "SORTIE"}).json()
    employee = client.post("/api/employees", headers=admin, json={
        "matricule": "EMP-0042", "last_name": "Ngono", "first_name": "Paul"}).json()
    client.put("/api/authorizations", headers=admin,
               json={"employee_id": employee["id"], "zone_id": zone["id"]})
    badge = client.post("/api/badges", headers=admin, json={"employee_id": employee["id"]}).json()
    token = client.get(f"/api/badges/{badge['id']}/qr-token", headers=admin).json()["token"]
    return {"zone": zone, "entry": entry, "exit": exit_, "employee": employee,
            "badge": badge, "token": token}
