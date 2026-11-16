"""Anti-passback under simultaneous scans (meaningful on PostgreSQL: row lock)."""
import os
from concurrent.futures import ThreadPoolExecutor

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("BHH_TEST_DATABASE_URL", "sqlite").startswith("sqlite"),
    reason="needs a real PostgreSQL (BHH_TEST_DATABASE_URL)",
)


def test_double_scan_race_lets_only_one_entry_through(client, agent, world):
    def hit(_):
        return client.post("/api/scan", headers=agent,
                           json={"checkpoint_id": world["entry"]["id"], "token": world["token"]}).json()["verdict"]

    with ThreadPoolExecutor(max_workers=8) as pool:
        verdicts = list(pool.map(hit, range(8)))
    assert verdicts.count("AUTORISE") == 1, verdicts
