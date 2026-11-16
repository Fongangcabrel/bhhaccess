"""Pure unit tests of the decision rules: no database, no HTTP."""
from datetime import UTC, datetime, timedelta

import pytest

from app.domain.enums import (
    AntiPassbackMode,
    BadgeStatus,
    Direction,
    EmployeeStatus,
    Flag,
    Verdict,
)
from app.domain.rules import ScanContext, build_default_engine

NOW = datetime(2026, 11, 11, 8, 0, tzinfo=UTC)


def ctx(**overrides) -> ScanContext:
    base = dict(  # noqa: C408
        now=NOW, direction=Direction.ENTRY, badge_status=BadgeStatus.ACTIVE, badge_version=1,
        token_version=1, badge_expires_at=None, employee_status=EmployeeStatus.ACTIVE,
        zone_mode=AntiPassbackMode.DISABLED, is_authorized_for_zone=True, has_presence=False,
    )
    base.update(overrides)
    return ScanContext(**base)


engine = build_default_engine()


@pytest.mark.parametrize("overrides, verdict", [
    ({}, Verdict.AUTHORIZED),
    ({"badge_status": BadgeStatus.REVOKED}, Verdict.DENIED_REVOKED),
    ({"token_version": 0}, Verdict.DENIED_REVOKED),  # old QR after re-issue
    ({"badge_expires_at": NOW - timedelta(days=1)}, Verdict.DENIED_EXPIRED),
    ({"employee_status": EmployeeStatus.SUSPENDED}, Verdict.DENIED_EMPLOYEE_INACTIVE),
    ({"is_authorized_for_zone": False}, Verdict.DENIED_ZONE),
    ({"zone_mode": AntiPassbackMode.STRICT, "has_presence": True}, Verdict.DENIED_ANTIPASSBACK),
])
def test_entry_verdicts(overrides, verdict):
    assert engine.decide(ctx(**overrides)).verdict == verdict


def test_soft_antipassback_allows_but_flags():
    decision = engine.decide(ctx(zone_mode=AntiPassbackMode.SOFT, has_presence=True))
    assert decision.verdict == Verdict.AUTHORIZED
    assert decision.flags == (Flag.DOUBLE_ENTRY,)


def test_revocation_wins_over_zone_denial():
    decision = engine.decide(ctx(badge_status=BadgeStatus.REVOKED, is_authorized_for_zone=False))
    assert decision.verdict == Verdict.DENIED_REVOKED


@pytest.mark.parametrize("overrides, flag", [
    ({"badge_status": BadgeStatus.REVOKED}, Flag.EXIT_BADGE_REVOKED),
    ({"badge_expires_at": NOW - timedelta(days=1)}, Flag.EXIT_BADGE_EXPIRED),
    ({"employee_status": EmployeeStatus.SUSPENDED}, Flag.EXIT_EMPLOYEE_SUSPENDED),
    ({"zone_mode": AntiPassbackMode.SOFT, "has_presence": False}, Flag.EXIT_WITHOUT_ENTRY),
])
def test_exit_is_never_refused_only_flagged(overrides, flag):
    decision = engine.decide(ctx(direction=Direction.EXIT, **overrides))
    assert decision.verdict == Verdict.EXIT_RECORDED
    assert flag in decision.flags


def test_clean_exit_has_no_flag():
    decision = engine.decide(ctx(direction=Direction.EXIT, zone_mode=AntiPassbackMode.STRICT,
                                 has_presence=True))
    assert decision.verdict == Verdict.EXIT_RECORDED and decision.flags == ()
