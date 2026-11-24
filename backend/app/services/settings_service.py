"""System configuration changed in the console (system.config), read live by the services.

Each setting has a default coming from the installation (environment ``BHH_...``); a value saved
in the console overrides it until it is put back to the default. Every change is audited.
"""
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.exceptions import DomainError
from app.models.session import AppSetting
from app.services.alert_service import AlertRules
from app.services.audit_service import AuditService


@dataclass(frozen=True)
class SettingSpec:
    key: str
    group: str
    label: str
    unit: str
    minimum: int
    maximum: int
    env: str  # attribute of app.core.config.Settings giving the installation default


SPECS: list[SettingSpec] = [
    SettingSpec("session.access_minutes", "Sessions", "Durée d'un jeton d'accès", "min", 1, 120,
                "access_token_minutes"),
    SettingSpec("session.refresh_hours", "Sessions", "Durée maximale d'une session (renouvelée sans reconnexion)",
                "h", 1, 72, "refresh_token_hours"),
    SettingSpec("alerts.default_seconds_between_units", "Alertes",
                "Temps de trajet par défaut entre deux unités", "s", 0, 86_400, "alert_default_seconds_between_units"),
    SettingSpec("alerts.burst_count", "Alertes", "Rafale : nombre de scans d'un badge", "scans", 2, 100,
                "alert_burst_count"),
    SettingSpec("alerts.burst_seconds", "Alertes", "Rafale : en moins de", "s", 5, 3_600, "alert_burst_seconds"),
    SettingSpec("alerts.refusal_count", "Alertes", "Refus répétés : nombre de refus", "refus", 2, 100,
                "alert_refusal_count"),
    SettingSpec("alerts.refusal_minutes", "Alertes", "Refus répétés : en moins de", "min", 1, 1_440,
                "alert_refusal_minutes"),
]
BY_KEY = {spec.key: spec for spec in SPECS}


def defaults_from(settings) -> dict[str, int]:
    """Installation defaults, read once from the environment settings."""
    return {spec.key: int(getattr(settings, spec.env)) for spec in SPECS}


class SettingsService:
    def __init__(self, session: Session, defaults: dict[str, int], clock: Clock,
                 audit: AuditService | None = None) -> None:
        self._session = session
        self._defaults = defaults
        self._clock = clock
        self._audit = audit

    def _saved(self) -> dict[str, AppSetting]:
        return {row.key: row for row in self._session.scalars(select(AppSetting))}

    def values(self) -> dict[str, int]:
        saved = self._saved()
        return {spec.key: int(saved[spec.key].value) if spec.key in saved else self._defaults[spec.key]
                for spec in SPECS}

    def get(self, key: str) -> int:
        row = self._session.get(AppSetting, key)
        return int(row.value) if row is not None else self._defaults[key]

    def describe(self) -> list[dict]:
        saved = self._saved()
        return [{
            "key": spec.key, "group": spec.group, "label": spec.label, "unit": spec.unit,
            "minimum": spec.minimum, "maximum": spec.maximum, "default": self._defaults[spec.key],
            "value": int(saved[spec.key].value) if spec.key in saved else self._defaults[spec.key],
            "customised": spec.key in saved,
        } for spec in SPECS]

    def update(self, actor_id: int, changes: dict[str, int | None]) -> list[dict]:
        """``None`` puts a setting back to its installation default. All checked before anything is saved."""
        for key, value in changes.items():
            spec = BY_KEY.get(key)
            if spec is None:
                raise DomainError(f"Réglage inconnu : {key}")
            if value is not None and not spec.minimum <= value <= spec.maximum:
                raise DomainError(f"Valeur hors limites : {spec.label} ({spec.minimum} à {spec.maximum} {spec.unit})")
        before, now = self.values(), self._clock.now()
        for key, value in changes.items():
            row = self._session.get(AppSetting, key)
            if value is None or value == self._defaults[key]:
                if row is not None:
                    self._session.delete(row)
            elif row is None:
                self._session.add(AppSetting(key=key, value=value, updated_at=now, updated_by=actor_id))
            else:
                row.value, row.updated_at, row.updated_by = value, now, actor_id
        self._session.flush()
        after = self.values()
        changed = {k for k in after if after[k] != before[k]}
        if changed and self._audit is not None:
            self._audit.record(actor_id, "settings.update", "configuration",
                               before={k: before[k] for k in sorted(changed)},
                               after={k: after[k] for k in sorted(changed)})
        return self.describe()

    def alert_rules(self) -> AlertRules:
        v = self.values()
        return AlertRules(default_seconds_between_units=v["alerts.default_seconds_between_units"],
                          burst_count=v["alerts.burst_count"], burst_seconds=v["alerts.burst_seconds"],
                          refusal_count=v["alerts.refusal_count"], refusal_minutes=v["alerts.refusal_minutes"])
