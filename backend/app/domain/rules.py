"""Scan decision rules (Strategy + Chain of Responsibility).

* Open/Closed: add a business rule by writing a new ``Rule`` and registering it in
  ``build_default_engine`` - the engine and the scan service never change.
* Single responsibility: each rule judges one thing.
* The rules are pure: they receive a ``ScanContext`` and touch no database.

An entry can be refused. An exit is never refused (the person must always be able to leave):
the same rules only raise *flags* for it.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from app.domain.enums import (
    AntiPassbackMode,
    BadgeStatus,
    Direction,
    EmployeeStatus,
    Flag,
    Verdict,
)


@dataclass(frozen=True)
class ScanContext:
    now: datetime
    direction: Direction
    badge_status: BadgeStatus
    badge_version: int
    token_version: int
    badge_expires_at: datetime | None
    employee_status: EmployeeStatus
    zone_mode: AntiPassbackMode
    is_authorized_for_zone: bool
    has_presence: bool
    # The authorisation exists but is not usable now (dates or time slots), see access_window.
    zone_window_refusal: str | None = None


@dataclass(frozen=True)
class RuleResult:
    refusal: Verdict | None = None
    flags: tuple[Flag, ...] = ()


OK = RuleResult()


class Rule(Protocol):
    def on_entry(self, ctx: ScanContext) -> RuleResult: ...
    def on_exit(self, ctx: ScanContext) -> RuleResult: ...


class BaseRule:
    """Neutral defaults so a rule only implements what it cares about."""

    def on_entry(self, ctx: ScanContext) -> RuleResult:
        return OK

    def on_exit(self, ctx: ScanContext) -> RuleResult:
        return OK


class BadgeRevokedRule(BaseRule):
    """Revoked badge, or an old QR whose version was superseded by a re-issue."""

    @staticmethod
    def _is_revoked(ctx: ScanContext) -> bool:
        return ctx.badge_status == BadgeStatus.REVOKED or ctx.token_version != ctx.badge_version

    def on_entry(self, ctx: ScanContext) -> RuleResult:
        return RuleResult(refusal=Verdict.DENIED_REVOKED) if self._is_revoked(ctx) else OK

    def on_exit(self, ctx: ScanContext) -> RuleResult:
        return RuleResult(flags=(Flag.EXIT_BADGE_REVOKED,)) if self._is_revoked(ctx) else OK


class BadgeExpiredRule(BaseRule):
    @staticmethod
    def _is_expired(ctx: ScanContext) -> bool:
        return ctx.badge_expires_at is not None and ctx.badge_expires_at <= ctx.now

    def on_entry(self, ctx: ScanContext) -> RuleResult:
        return RuleResult(refusal=Verdict.DENIED_EXPIRED) if self._is_expired(ctx) else OK

    def on_exit(self, ctx: ScanContext) -> RuleResult:
        return RuleResult(flags=(Flag.EXIT_BADGE_EXPIRED,)) if self._is_expired(ctx) else OK


class EmployeeActiveRule(BaseRule):
    def on_entry(self, ctx: ScanContext) -> RuleResult:
        if ctx.employee_status != EmployeeStatus.ACTIVE:
            return RuleResult(refusal=Verdict.DENIED_EMPLOYEE_INACTIVE)
        return OK

    def on_exit(self, ctx: ScanContext) -> RuleResult:
        if ctx.employee_status != EmployeeStatus.ACTIVE:
            return RuleResult(flags=(Flag.EXIT_EMPLOYEE_SUSPENDED,))
        return OK


class ZoneAuthorizationRule(BaseRule):
    """No authorisation, or one outside its dates / time slots: REFUSE_ZONE (the SRS keeps 8
    verdicts; the precise reason goes to the journal and to the agent's screen)."""

    def on_entry(self, ctx: ScanContext) -> RuleResult:
        if not ctx.is_authorized_for_zone or ctx.zone_window_refusal is not None:
            return RuleResult(refusal=Verdict.DENIED_ZONE)
        return OK


class AntiPassbackRule(BaseRule):
    """Soft mode flags a second entry; strict mode refuses it until someone unblocks."""

    def on_entry(self, ctx: ScanContext) -> RuleResult:
        if not ctx.has_presence or ctx.zone_mode == AntiPassbackMode.DISABLED:
            return OK
        if ctx.zone_mode == AntiPassbackMode.STRICT:
            return RuleResult(refusal=Verdict.DENIED_ANTIPASSBACK)
        return RuleResult(flags=(Flag.DOUBLE_ENTRY,))

    def on_exit(self, ctx: ScanContext) -> RuleResult:
        if ctx.zone_mode != AntiPassbackMode.DISABLED and not ctx.has_presence:
            return RuleResult(flags=(Flag.EXIT_WITHOUT_ENTRY,))
        return OK


@dataclass(frozen=True)
class Decision:
    verdict: Verdict
    flags: tuple[Flag, ...] = field(default_factory=tuple)


class DecisionEngine:
    """Runs the rules in order. First refusal wins on entry; flags accumulate."""

    def __init__(self, rules: list[Rule]) -> None:
        self._rules = rules

    def decide(self, ctx: ScanContext) -> Decision:
        if ctx.direction == Direction.EXIT:
            return self._decide_exit(ctx)
        return self._decide_entry(ctx)

    def _decide_entry(self, ctx: ScanContext) -> Decision:
        flags: list[Flag] = []
        for rule in self._rules:
            result = rule.on_entry(ctx)
            flags.extend(result.flags)
            if result.refusal is not None:
                return Decision(result.refusal, tuple(flags))
        return Decision(Verdict.AUTHORIZED, tuple(flags))

    def _decide_exit(self, ctx: ScanContext) -> Decision:
        flags: list[Flag] = []
        for rule in self._rules:
            flags.extend(rule.on_exit(ctx).flags)
        return Decision(Verdict.EXIT_RECORDED, tuple(flags))


def build_default_engine() -> DecisionEngine:
    return DecisionEngine(
        [
            BadgeRevokedRule(),
            BadgeExpiredRule(),
            EmployeeActiveRule(),
            ZoneAuthorizationRule(),
            AntiPassbackRule(),
        ]
    )
