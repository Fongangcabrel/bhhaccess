"""Use case: a gate agent scans a badge (or types a matricule) at a checkpoint."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from app.core.clock import Clock
from app.core.exceptions import ConflictError, InvalidTokenError, NotFoundError
from app.domain import access_window
from app.domain.enums import AntiPassbackMode, Direction, EmployeeStatus, Flag, ScanMethod, Verdict
from app.domain.qr_token import TokenSigner
from app.domain.rules import DecisionEngine, ScanContext
from app.models import AccessLog, Badge, Checkpoint, Employee, ZonePresence
from app.repositories.repositories import (
    AccessLogRepository,
    AssignmentRepository,
    AuthorizationRepository,
    BadgeRepository,
    CheckpointRepository,
    EmployeeRepository,
    PresenceRepository,
    ZoneRepository,
)

if TYPE_CHECKING:
    from app.services.alert_service import AlertService


@dataclass(frozen=True)
class ScanSource:
    """Who performed the scan: a paired phone (normal case) or a logged-in back-office user."""

    device_id: int | None = None
    operator_id: int | None = None


@dataclass(frozen=True)
class ScanResult:
    verdict: Verdict
    flags: tuple[Flag, ...]
    occurred_at: datetime
    log_id: int
    direction: Direction
    zone_name: str
    checkpoint_name: str
    employee: Employee | None  # None when the QR itself is unreadable/forged
    warning: str | None = None
    last_entry_at: datetime | None = None
    last_entry_checkpoint: str | None = None
    detail: str | None = None  # precise refusal shown to the agent (e.g. "Hors des horaires autorisés")
    alert: str | None = None  # alert raised by this scan, announced at the post
    repeat: bool = False  # same badge, same post, < 3 s: the first answer again, nothing new recorded


# Internal reasons behind a "QR non reconnu": written in the journal, never shown to the agent.
REASON_BAD_SIGNATURE = "signature_invalide"
REASON_UNKNOWN_BADGE = "badge_inconnu"
REASON_ARCHIVED = "employe_archive"
MANUAL = "saisie manuelle"
WARNING_DOUBLE_ENTRY = "DOUBLE_ENTREE"
# Announced at the post, most serious first (EMPLOYE_ARCHIVE stays hidden from the agent).
# A badge read twice at the same post this fast is one passage (double frame, network retry).
REPEAT_WINDOW = timedelta(seconds=3)
ALERT_PRIORITY = ("SIMULTANEE", "BADGE_REVOQUE", "HORS_HORAIRE", "REFUS_REPETES", "RAFALE")


def most_serious(alerts) -> str | None:
    kinds = {a.type.value for a in alerts}
    return next((k for k in ALERT_PRIORITY if k in kinds), None)


class ScanService:
    def __init__(self, *, badges: BadgeRepository, employees: EmployeeRepository,
                 checkpoints: CheckpointRepository, zones: ZoneRepository,
                 authorizations: AuthorizationRepository, presences: PresenceRepository,
                 logs: AccessLogRepository, assignments: AssignmentRepository, signer: TokenSigner,
                 engine: DecisionEngine, clock: Clock, timezone: str = "Africa/Douala",
                 alerts: "AlertService | None" = None) -> None:
        self._alerts = alerts
        self._badges = badges
        self._employees = employees
        self._checkpoints = checkpoints
        self._zones = zones
        self._authorizations = authorizations
        self._presences = presences
        self._logs = logs
        self._assignments = assignments
        self._signer = signer
        self._engine = engine
        self._clock = clock
        self._tz = ZoneInfo(timezone)

    # --- entry points ------------------------------------------------------
    def scan_qr(self, source: ScanSource, checkpoint_id: int, token: str) -> ScanResult:
        checkpoint = self._require_checkpoint(checkpoint_id)
        try:
            claims = self._signer.verify(token)
        except InvalidTokenError:
            return self._log_unreadable(source, checkpoint, REASON_BAD_SIGNATURE)
        badge = self._badges.get(claims.badge_id)
        if badge is None:
            return self._log_unreadable(source, checkpoint, REASON_UNKNOWN_BADGE)
        return self._process(source, checkpoint, badge, token_version=claims.version, method=ScanMethod.QR)

    def scan_manual(self, source: ScanSource, checkpoint_id: int, matricule: str) -> ScanResult:
        """Fallback when the QR is damaged: the agent types the matricule."""
        checkpoint = self._require_checkpoint(checkpoint_id)
        employee = self._employees.by_matricule(matricule.strip())
        if employee is not None and employee.status == EmployeeStatus.ARCHIVED:
            # Same answer as the archived person's QR: the agent learns nothing more.
            return self._log_unreadable(source, checkpoint, f"{REASON_ARCHIVED} ({MANUAL})", employee_id=employee.id,
                                        method=ScanMethod.MANUAL)
        badge = self._badges.active_for_employee(employee.id) if employee else None
        if badge is None:
            raise NotFoundError("Aucun badge actif pour ce matricule")
        return self._process(source, checkpoint, badge, token_version=badge.version, reason=MANUAL,
                             method=ScanMethod.MANUAL)

    # --- internals ---------------------------------------------------------
    def _process(self, source: ScanSource, checkpoint: Checkpoint, badge: Badge, *,
                 token_version: int, method: ScanMethod, reason: str | None = None) -> ScanResult:
        now = self._clock.now()
        employee = self._employees.get_locked(badge.employee_id)  # serialise scans of one person
        previous = self._logs.repeat_of(badge.id, checkpoint.id, now - REPEAT_WINDOW)
        if previous is not None:  # checked under the lock: two simultaneous requests are one passage too
            return self._repeat(previous, checkpoint, employee)
        if employee.status == EmployeeStatus.ARCHIVED:
            # Entry or exit: "QR non reconnu", no identity; the real reason stays in the journal.
            reason_text = REASON_ARCHIVED if reason is None else f"{REASON_ARCHIVED} ({reason})"
            return self._log_unreadable(source, checkpoint, reason_text, badge_id=badge.id, employee_id=employee.id,
                                        method=method)
        zone = checkpoint.zone
        presence = self._presences.get_locked(employee.id, zone.id)
        authorization = self._authorizations.find(employee.id, zone.id)
        window = None
        if authorization is not None and checkpoint.direction == Direction.ENTRY:
            window = access_window.check(now, self._tz, authorization.valid_from, authorization.valid_until,
                                         authorization.slots)

        ctx = ScanContext(
            now=now, direction=checkpoint.direction,
            badge_status=badge.status, badge_version=badge.version, token_version=token_version,
            badge_expires_at=badge.expires_at, employee_status=employee.status,
            zone_mode=zone.antipassback_mode,
            is_authorized_for_zone=authorization is not None,
            has_presence=presence is not None,
            zone_window_refusal=window.value if window else None,
        )
        decision = self._engine.decide(ctx)
        detail = None
        if decision.verdict == Verdict.DENIED_ZONE and window is not None:
            detail = self._window_detail(window, authorization)
            reason = window.value if reason is None else f"{window.value} ({reason})"
        flags = list(decision.flags)
        passed = decision.verdict in (Verdict.AUTHORIZED, Verdict.EXIT_RECORDED)
        if passed and self._follows_unblock(employee.id, zone.id):
            flags.append(Flag.UNBLOCKED)  # first scan through after a manual unblock (TRD §9)
        self._update_presence(decision.verdict, ctx, presence, employee.id, checkpoint, now)

        log = self._logs.add(
            AccessLog(
                occurred_at=now, employee_id=employee.id, badge_id=badge.id,
                zone_id=zone.id, checkpoint_id=checkpoint.id, direction=checkpoint.direction,
                verdict=decision.verdict, flags=[f.value for f in flags], method=method,
                reason=reason, **self._attribution(source, checkpoint),
            )
        )
        alert = None
        if self._alerts is not None:  # reuse / abnormal use: a signal, never a change of verdict
            raised = self._alerts.after_scan(log, checkpoint, window_refusal=window.value if window else None)
            alert = most_serious(raised)
        warning = None
        if Flag.DOUBLE_ENTRY in flags and zone.antipassback_warn_agent:
            warning = WARNING_DOUBLE_ENTRY
        # "Déjà entré" and double entry: remind the agent when the person came in (UX 3.2).
        show_entry = presence is not None and (decision.verdict == Verdict.DENIED_ANTIPASSBACK or warning)
        return ScanResult(decision.verdict, tuple(flags), now, log.id, checkpoint.direction,
                          zone.name, checkpoint.name, employee, warning,
                          presence.entered_at if show_entry else None,
                          self._checkpoint_name(presence.checkpoint_id) if show_entry else None, detail,
                          alert)

    @staticmethod
    def _window_detail(window: access_window.WindowRefusal, authorization) -> str:
        detail = access_window.AGENT_MESSAGE[window]
        if window == access_window.WindowRefusal.OUTSIDE_HOURS and authorization is not None:
            detail += " : " + " · ".join(access_window.describe_slot(s) for s in authorization.slots)
        return detail

    def _repeat(self, log: AccessLog, checkpoint: Checkpoint, employee: Employee) -> ScanResult:
        """The answer given to the first scan, rebuilt from its journal line: no new line,
        no alert, no change of presence (TRD: one passage = one line)."""
        zone = checkpoint.zone
        if log.verdict == Verdict.DENIED_INVALID:  # e.g. an archived person's QR: still nothing about them
            return ScanResult(log.verdict, (), log.occurred_at, log.id, log.direction, zone.name, checkpoint.name,
                              None, repeat=True)
        flags = tuple(Flag(f) for f in log.flags)
        warning = WARNING_DOUBLE_ENTRY if Flag.DOUBLE_ENTRY in flags and zone.antipassback_warn_agent else None
        presence = self._presences.get_locked(employee.id, zone.id)
        show_entry = presence is not None and (log.verdict == Verdict.DENIED_ANTIPASSBACK or warning)
        detail = None
        window = next((w for w in access_window.WindowRefusal if (log.reason or "").startswith(w.value)), None)
        if log.verdict == Verdict.DENIED_ZONE and window is not None:
            detail = self._window_detail(window, self._authorizations.find(employee.id, zone.id))
        return ScanResult(log.verdict, flags, log.occurred_at, log.id, log.direction, zone.name, checkpoint.name,
                          employee, warning,
                          presence.entered_at if show_entry else None,
                          self._checkpoint_name(presence.checkpoint_id) if show_entry else None,
                          detail, repeat=True)

    def _checkpoint_name(self, checkpoint_id: int | None) -> str | None:
        checkpoint = self._checkpoints.get(checkpoint_id) if checkpoint_id else None
        return checkpoint.name if checkpoint else None

    def _follows_unblock(self, employee_id: int, zone_id: int) -> bool:
        last = self._logs.last_decisive(employee_id, zone_id)
        return last is not None and last.method == ScanMethod.CONSOLE

    def _attribution(self, source: ScanSource, checkpoint: Checkpoint) -> dict:
        """Who scanned (device/operator) and which agent was posted here at that moment."""
        assignment = self._assignments.open_for_checkpoint(checkpoint.id)
        return {
            "device_id": source.device_id, "operator_id": source.operator_id,
            "agent_id": assignment.agent_id if assignment else None,
            "agent_name": assignment.agent.full_name if assignment else None,
        }

    def _update_presence(self, verdict: Verdict, ctx: ScanContext, presence: ZonePresence | None,
                         employee_id: int, checkpoint: Checkpoint, now: datetime) -> None:
        if ctx.zone_mode == AntiPassbackMode.DISABLED:
            return
        if verdict == Verdict.AUTHORIZED and presence is None:
            self._presences.add(ZonePresence(
                employee_id=employee_id, zone_id=checkpoint.zone_id,
                entered_at=now, checkpoint_id=checkpoint.id))
        elif verdict == Verdict.EXIT_RECORDED and presence is not None:
            self._presences.remove(presence)

    def _log_unreadable(self, source: ScanSource, checkpoint: Checkpoint, reason: str, *,
                        badge_id: int | None = None, employee_id: int | None = None,
                        method: ScanMethod = ScanMethod.QR) -> ScanResult:
        """REFUSE_INVALIDE: nothing about the person goes back to the phone."""
        now = self._clock.now()
        log = self._logs.add(
            AccessLog(
                occurred_at=now, zone_id=checkpoint.zone_id, checkpoint_id=checkpoint.id,
                direction=checkpoint.direction, verdict=Verdict.DENIED_INVALID,
                employee_id=employee_id, badge_id=badge_id, reason=reason, method=method,
                flags=[], **self._attribution(source, checkpoint),
            )
        )
        if self._alerts is not None and badge_id is not None and reason.startswith(REASON_ARCHIVED):
            self._alerts.after_scan(log, checkpoint, archived=True)
        return ScanResult(Verdict.DENIED_INVALID, (), now, log.id, checkpoint.direction,
                          checkpoint.zone.name, checkpoint.name, None)

    def _require_checkpoint(self, checkpoint_id: int) -> Checkpoint:
        checkpoint = self._checkpoints.get(checkpoint_id)
        if checkpoint is None:
            raise NotFoundError("Point de contrôle introuvable")
        if not checkpoint.usable:
            raise ConflictError("Ce poste est désactivé : choisissez un autre poste")
        return checkpoint
