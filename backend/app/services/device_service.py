"""Phones paired once with a one-time code: afterwards they scan without any login."""
import hashlib
import secrets
from datetime import timedelta

from app.core.clock import Clock
from app.core.exceptions import AuthenticationError, ConflictError, DomainError, ForbiddenError, NotFoundError
from app.core.rate_limit import FailureLimiter
from app.models import Checkpoint, Device, DeviceScope
from app.repositories.repositories import (
    AccessLogRepository,
    CheckpointRepository,
    DeviceRepository,
    UnitRepository,
    ZoneRepository,
)
from app.services.audit_service import AuditService

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I: easy to read aloud
CODE_LENGTH = 8
CODE_VALIDITY = timedelta(minutes=15)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def normalize_code(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())


class DeviceService:
    def __init__(self, devices: DeviceRepository, audit: AuditService, clock: Clock,
                 limiter: FailureLimiter, logs: AccessLogRepository, units: UnitRepository | None = None,
                 zones: ZoneRepository | None = None, checkpoints: CheckpointRepository | None = None) -> None:
        self._units, self._zones, self._checkpoints = units, zones, checkpoints
        self._devices = devices
        self._logs = logs
        self._audit = audit
        self._clock = clock
        self._limiter = limiter

    # --- perimeter (tâche 41) ---------------------------------------------------
    def set_scope(self, actor_id: int, device_id: int, unit_ids: list[int], zone_ids: list[int],
                  checkpoint_ids: list[int]) -> Device:
        """What the phone covers. A ticked unit or zone already includes what is inside it,
        so those are not stored twice. Nothing ticked = the whole site."""
        device = self._require(device_id)
        units = {i: self._units.get(i) for i in set(unit_ids)}
        zones = {i: self._zones.get(i) for i in set(zone_ids)}
        posts = {i: self._checkpoints.get(i) for i in set(checkpoint_ids)}
        if None in units.values() or None in zones.values() or None in posts.values():
            raise NotFoundError("Unité, zone ou poste introuvable")
        zones = {i: z for i, z in zones.items() if z.unit_id not in units}
        posts = {i: c for i, c in posts.items() if c.zone_id not in zones and c.zone.unit_id not in units}
        before = device.scope_summary
        device.scope[:] = ([DeviceScope(unit_id=i) for i in sorted(units)]
                           + [DeviceScope(zone_id=i) for i in sorted(zones)]
                           + [DeviceScope(checkpoint_id=i) for i in sorted(posts)])
        self._devices.flush()
        self._devices.refresh(device)
        if device.scope_summary != before:
            self._audit.record(actor_id, "device.scope", device.name, before={"scope": before},
                               after={"scope": device.scope_summary})
        return device

    def allowed_checkpoints(self, device: Device, checkpoints: list[Checkpoint]) -> list[Checkpoint]:
        return [c for c in checkpoints if device.covers(c)]

    def require_covers(self, device: Device, checkpoint_id: int) -> None:
        """A phone only scans inside its perimeter, even if someone forges the request."""
        checkpoint = self._checkpoints.get(checkpoint_id) if self._checkpoints else None
        if checkpoint is not None and not device.covers(checkpoint):
            raise ForbiddenError("Ce poste n'est pas dans le périmètre de ce téléphone")

    # --- back-office ---------------------------------------------------------
    def create(self, actor_id: int, name: str) -> tuple[Device, str]:
        name = name.strip()
        if not name:
            raise DomainError("Nom de l'appareil obligatoire")
        device = self._devices.add(Device(name=name, created_at=self._clock.now()))
        code = self._issue_code(device)
        self._audit.record(actor_id, "device.create", name)
        return device, code

    def new_code(self, actor_id: int, device_id: int) -> tuple[Device, str]:
        """Re-pair a phone (lost, replaced): the previous token stops working immediately."""
        device = self._require(device_id)
        device.token_hash = None
        device.paired_at = None
        device.revoked_at = None
        code = self._issue_code(device)
        self._audit.record(actor_id, "device.recode", device.name)
        return device, code

    def revoke(self, actor_id: int, device_id: int) -> Device:
        device = self._require(device_id)
        device.revoked_at = self._clock.now()
        device.code_hash = None
        device.code_expires_at = None
        self._audit.record(actor_id, "device.revoke", device.name)
        return device

    def rename(self, actor_id: int, device_id: int, name: str) -> Device:
        device, name = self._require(device_id), name.strip()
        if not name:
            raise DomainError("Nom de l'appareil obligatoire")
        old, device.name = device.name, name
        self._devices.flush()
        self._audit.record(actor_id, "device.rename", name, before={"name": old}, after={"name": name})
        return device

    def set_voice(self, actor_id: int, device_id: int, enabled: bool) -> Device:
        device = self._require(device_id)
        before, device.voice_enabled = device.voice_enabled, enabled
        self._devices.flush()
        self._audit.record(actor_id, "device.voice", device.name, before={"voice": before}, after={"voice": enabled})
        return device

    def delete(self, actor_id: int, device_id: int) -> None:
        """Only a phone that never scanned; otherwise block it (the journal names it)."""
        device = self._require(device_id)
        if self._logs.used_by(device_id=device.id):
            raise ConflictError("Ce téléphone a déjà scanné : bloquez-le plutôt, le journal le cite")
        self._devices.remove(device)
        self._audit.record(actor_id, "device.delete", device.name)

    def all(self) -> list[Device]:
        return self._devices.list(limit=1000)

    # --- phone side ----------------------------------------------------------
    def pair(self, code: str, client_key: str) -> tuple[Device, str]:
        self._limiter.check(client_key)
        device = self._devices.by_code_hash(_hash(normalize_code(code)))
        now = self._clock.now()
        if (device is None or device.revoked_at is not None
                or device.code_expires_at is None or device.code_expires_at < now):
            self._limiter.fail(client_key)
            raise AuthenticationError("Code invalide ou expiré")
        token = secrets.token_urlsafe(32)
        device.token_hash = _hash(token)
        device.paired_at = now
        device.last_seen_at = now
        device.code_hash = None  # single use
        device.code_expires_at = None
        self._audit.record(None, "device.pair", device.name)
        return device, token

    def authenticate(self, token: str | None) -> Device:
        device = self._devices.by_token_hash(_hash(token)) if token else None
        if device is None or device.revoked_at is not None:
            raise AuthenticationError("Appareil non reconnu : appairez à nouveau ce téléphone")
        device.last_seen_at = self._clock.now()
        return device

    # --- internals -----------------------------------------------------------
    def _issue_code(self, device: Device) -> str:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        device.code_hash = _hash(code)
        device.code_expires_at = self._clock.now() + CODE_VALIDITY
        return code

    def _require(self, device_id: int) -> Device:
        device = self._devices.get(device_id)
        if device is None:
            raise NotFoundError("Appareil introuvable")
        return device
