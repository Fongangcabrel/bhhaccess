"""Suspicious badge use (SRS FR-90 to FR-93, TRD §9 « Détection de réutilisation »).

Checked right after each scan is written, in the same transaction (indexed queries):

* SIMULTANEE      the badge was scanned at another post faster than the walking time between the
                  two posts (configured per pair, otherwise a default between different units);
* BADGE_REVOQUE   a revoked or replaced badge was presented (every attempt);
* EMPLOYE_ARCHIVE the QR of an archived employee was presented (every attempt);
* HORS_HORAIRE    an entry was tried outside the allowed time slots;
* RAFALE          many scans of the same badge in a few seconds;
* REFUS_REPETES   several refusals for the same badge in a few minutes.

An alert never changes the verdict: it is a signal for the security team, who acknowledge it or
revoke the badge from the alerts screen.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.exceptions import ConflictError, DomainError, NotFoundError
from app.domain.enums import AlertStatus, AlertType, Verdict
from app.models import AccessLog, Alert, Badge, Checkpoint, TravelTime
from app.services.audit_service import AuditService

PASSED = (Verdict.AUTHORIZED, Verdict.EXIT_RECORDED)


@dataclass(frozen=True)
class AlertRules:
    """Thresholds (environment: BHH_ALERT_...)."""

    default_seconds_between_units: int = 600  # two different sites: 10 min at least
    burst_count: int = 5
    burst_seconds: int = 60
    refusal_count: int = 3
    refusal_minutes: int = 10
    # The same signal is not repeated while an identical alert is still « nouvelle ».
    dedupe_minutes: dict | None = None

    def dedupe(self, kind: AlertType) -> int:
        defaults = {
            AlertType.SIMULTANEOUS: 2,
            AlertType.OUTSIDE_HOURS: 60,
            AlertType.BURST: 10,
            AlertType.REPEATED_REFUSALS: 30,
            AlertType.REVOKED_USE: 0,
            AlertType.ARCHIVED_USE: 0,
        }
        return (self.dedupe_minutes or defaults).get(kind, 0)


def _duration(seconds: float) -> str:
    seconds = int(round(seconds))
    if seconds < 60:
        return f"{seconds} s"
    minutes, rest = divmod(seconds, 60)
    return f"{minutes} min {rest:02d} s" if rest else f"{minutes} min"


class AlertService:
    def __init__(
        self, session: Session, audit: AuditService | None, clock: Clock, rules: AlertRules | None = None
    ) -> None:
        self._session = session
        self._audit = audit
        self._clock = clock
        self._rules = rules or AlertRules()

    # --- detection (called by the scan service) ------------------------------
    def after_scan(
        self, log: AccessLog, checkpoint: Checkpoint, *, window_refusal: str | None = None, archived: bool = False
    ) -> list[Alert]:
        if log.badge_id is None:
            return []
        created: list[Alert] = []
        if archived:
            created += self._raise(
                AlertType.ARCHIVED_USE,
                log,
                checkpoint,
                "QR d'un employé archivé présenté (« QR non reconnu » affiché à l'agent)",
            )
            return created
        if log.verdict == Verdict.DENIED_REVOKED:
            created += self._raise(
                AlertType.REVOKED_USE, log, checkpoint, "Badge révoqué ou remplacé présenté : vérifier qui le détient"
            )
        if window_refusal == "hors_horaire":
            created += self._raise(
                AlertType.OUTSIDE_HOURS, log, checkpoint, "Tentative d'entrée hors des horaires autorisés"
            )
        created += self._simultaneous(log, checkpoint)
        created += self._burst(log, checkpoint)
        created += self._repeated_refusals(log, checkpoint)
        return created

    def _simultaneous(self, log: AccessLog, checkpoint: Checkpoint) -> list[Alert]:
        previous = self._session.scalar(
            select(AccessLog)
            .where(AccessLog.badge_id == log.badge_id, AccessLog.id != log.id, AccessLog.occurred_at <= log.occurred_at)
            .order_by(AccessLog.occurred_at.desc(), AccessLog.id.desc())
            .limit(1)
        )
        if previous is None or previous.checkpoint_id == checkpoint.id:
            return []
        required = self.min_seconds(previous.checkpoint, checkpoint)
        elapsed = (log.occurred_at - previous.occurred_at).total_seconds()
        if required <= 0 or elapsed >= required:
            return []
        message = (
            f"Badge scanné à « {previous.checkpoint.name} » puis à « {checkpoint.name} » en {_duration(elapsed)}"
            f" (trajet minimum {_duration(required)}) : badge copié ou prêté ?"
        )
        return self._raise(
            AlertType.SIMULTANEOUS,
            log,
            checkpoint,
            message,
            previous_log_id=previous.id,
            previous_checkpoint=previous.checkpoint.name,
            elapsed_seconds=int(elapsed),
            required_seconds=required,
        )

    def _burst(self, log: AccessLog, checkpoint: Checkpoint) -> list[Alert]:
        since = log.occurred_at - timedelta(seconds=self._rules.burst_seconds)
        count = self._count(log.badge_id, since)
        if count < self._rules.burst_count:
            return []
        return self._raise(
            AlertType.BURST,
            log,
            checkpoint,
            f"{count} scans du même badge en moins de {_duration(self._rules.burst_seconds)}",
            scans=count,
        )

    def _repeated_refusals(self, log: AccessLog, checkpoint: Checkpoint) -> list[Alert]:
        if log.verdict in PASSED:
            return []
        since = log.occurred_at - timedelta(minutes=self._rules.refusal_minutes)
        count = self._count(log.badge_id, since, refused_only=True)
        if count < self._rules.refusal_count:
            return []
        return self._raise(
            AlertType.REPEATED_REFUSALS,
            log,
            checkpoint,
            f"{count} refus pour le même badge en moins de {self._rules.refusal_minutes} min",
            refusals=count,
        )

    def _count(self, badge_id: int, since: datetime, refused_only: bool = False) -> int:
        stmt = (
            select(func.count())
            .select_from(AccessLog)
            .where(AccessLog.badge_id == badge_id, AccessLog.occurred_at >= since)
        )
        if refused_only:
            stmt = stmt.where(AccessLog.verdict.not_in(PASSED))
        return self._session.scalar(stmt) or 0

    def _raise(self, kind: AlertType, log: AccessLog, checkpoint: Checkpoint, message: str, **detail) -> list[Alert]:
        minutes = self._rules.dedupe(kind)
        if minutes:
            recent = self._session.scalar(
                select(Alert.id)
                .where(
                    Alert.type == kind,
                    Alert.badge_id == log.badge_id,
                    Alert.status == AlertStatus.NEW,
                    Alert.created_at >= log.occurred_at - timedelta(minutes=minutes),
                )
                .limit(1)
            )
            if recent is not None:
                return []
        alert = Alert(
            created_at=log.occurred_at,
            type=kind,
            status=AlertStatus.NEW,
            badge_id=log.badge_id,
            employee_id=log.employee_id,
            access_log_id=log.id,
            checkpoint_id=checkpoint.id,
            message=message[:300],
            detail=detail,
        )
        self._session.add(alert)
        self._session.flush()
        return [alert]

    # --- travel times ----------------------------------------------------------
    def min_seconds(self, a: Checkpoint, b: Checkpoint) -> int:
        """Configured pair first; otherwise the default between two units; same unit: no check."""
        low, high = sorted((a.id, b.id))
        configured = self._session.scalar(
            select(TravelTime.min_seconds).where(TravelTime.checkpoint_a_id == low, TravelTime.checkpoint_b_id == high)
        )
        if configured is not None:
            return configured
        return self._rules.default_seconds_between_units if a.zone.unit_id != b.zone.unit_id else 0

    def travel_times(self) -> list[TravelTime]:
        return list(self._session.scalars(select(TravelTime).order_by(TravelTime.id)))

    def set_travel_time(self, actor_id: int, a_id: int, b_id: int, minutes: float) -> TravelTime:
        if a_id == b_id:
            raise DomainError("Choisissez deux postes différents")
        if minutes < 0 or minutes > 24 * 60:
            raise DomainError("Durée entre 0 et 1440 minutes")
        a, b = self._session.get(Checkpoint, a_id), self._session.get(Checkpoint, b_id)
        if a is None or b is None:
            raise NotFoundError("Poste introuvable")
        low, high = sorted((a_id, b_id))
        row = self._session.scalar(
            select(TravelTime).where(TravelTime.checkpoint_a_id == low, TravelTime.checkpoint_b_id == high)
        )
        seconds = int(round(minutes * 60))
        before = row.min_seconds if row else None
        if row is None:
            row = TravelTime(checkpoint_a_id=low, checkpoint_b_id=high, min_seconds=seconds)
            self._session.add(row)
        else:
            row.min_seconds = seconds
        self._session.flush()
        self._session.refresh(row)
        self._record(
            actor_id,
            "alert.travel_time",
            f"{row.checkpoint_a.name} ↔ {row.checkpoint_b.name}",
            before={"minutes": None if before is None else before / 60},
            after={"minutes": seconds / 60},
        )
        return row

    def delete_travel_time(self, actor_id: int, travel_id: int) -> None:
        row = self._session.get(TravelTime, travel_id)
        if row is None:
            raise NotFoundError("Temps de trajet introuvable")
        label = f"{row.checkpoint_a.name} ↔ {row.checkpoint_b.name}"
        self._session.delete(row)
        self._session.flush()
        self._record(actor_id, "alert.travel_time.delete", label)

    # --- handling (console) ------------------------------------------------------
    def search(self, status: AlertStatus | None, kind: AlertType | None, limit: int, offset: int) -> list[Alert]:
        stmt = select(Alert)
        if status is not None:
            stmt = stmt.where(Alert.status == status)
        if kind is not None:
            stmt = stmt.where(Alert.type == kind)
        stmt = stmt.order_by(Alert.created_at.desc(), Alert.id.desc()).limit(limit).offset(offset)
        return list(self._session.scalars(stmt).unique())

    def count_new(self) -> int:
        return self._session.scalar(select(func.count()).select_from(Alert).where(Alert.status == AlertStatus.NEW)) or 0

    def acknowledge(self, actor_id: int, alert_id: int, note: str | None) -> Alert:
        alert = self._get(alert_id)
        if alert.status == AlertStatus.ACKNOWLEDGED:
            raise ConflictError("Alerte déjà prise en compte")
        alert.status, alert.handled_by, alert.handled_at = AlertStatus.ACKNOWLEDGED, actor_id, self._clock.now()
        alert.note = (note or "").strip()[:300] or None
        self._session.flush()
        self._record(
            actor_id, "alert.ack", self._target(alert), alert_id=alert.id, type=alert.type.value, note=alert.note
        )
        return alert

    def badge_of(self, alert_id: int) -> Badge:
        alert = self._get(alert_id)
        badge = self._session.get(Badge, alert.badge_id) if alert.badge_id else None
        if badge is None:
            raise NotFoundError("Aucun badge lié à cette alerte")
        return badge

    def _get(self, alert_id: int) -> Alert:
        alert = self._session.get(Alert, alert_id)
        if alert is None:
            raise NotFoundError("Alerte introuvable")
        return alert

    @staticmethod
    def _target(alert: Alert) -> str:
        return alert.employee.matricule if alert.employee else f"alerte {alert.id}"

    def _record(self, actor_id: int, action: str, target: str, **detail) -> None:
        if self._audit is not None:
            self._audit.record(actor_id, action, target, **detail)
