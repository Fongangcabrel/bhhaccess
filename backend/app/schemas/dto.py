"""API data contracts (the "View" of MVC): what goes in and out as JSON."""
from datetime import date, datetime, time

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, computed_field

from app.domain.enums import (
    AlertStatus,
    AlertType,
    AntiPassbackMode,
    BadgeStatus,
    BulkAction,
    Direction,
    EmployeeStatus,
    Flag,
    OverrideEffect,
    RevocationReason,
    ScanMethod,
    Verdict,
    ZoneSensitivity,
)
from app.domain.permissions import Permission
from app.services.audit_labels import audit_label, describe_detail, describe_other
from app.services.audit_labels import changes as audit_changes
from app.services.presence_service import UnblockMode


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- auth -------------------------------------------------------------------
class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeOut(_Out):
    id: int
    username: str
    full_name: str
    role: str
    permissions: list[str]
    must_change_password: bool = False


class PasswordChangeIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class PasswordResetIn(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)


# --- employees --------------------------------------------------------------
class EmployeeIn(BaseModel):
    matricule: str = Field(min_length=1, max_length=40)
    last_name: str
    first_name: str
    job_title: str | None = None
    entity_id: int | None = None
    department_id: int | None = None
    extra: dict = Field(default_factory=dict)


class EmployeeOut(_Out):
    id: int
    matricule: str
    last_name: str
    first_name: str
    job_title: str | None
    entity_id: int | None
    department_id: int | None
    entity_name: str | None
    department_name: str | None
    status: EmployeeStatus
    archived_at: datetime | None = None
    archive_reason: str | None = None
    has_photo: bool = False
    photo_url: str | None = None  # signed, valid 60 s


class EmployeeUpdateIn(BaseModel):
    """Partial edit: only the fields sent are changed."""

    matricule: str | None = Field(default=None, min_length=1, max_length=40)
    last_name: str | None = Field(default=None, min_length=1, max_length=120)
    first_name: str | None = Field(default=None, min_length=1, max_length=120)
    job_title: str | None = Field(default=None, max_length=120)
    entity_id: int | None = None
    department_id: int | None = None
    extra: dict | None = None


class EmployeeStatusIn(BaseModel):
    status: EmployeeStatus


class ArchiveIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


# --- badges -----------------------------------------------------------------
class BadgeIssueIn(BaseModel):
    employee_id: int
    expires_at: datetime | None = None


class BadgeRevokeIn(BaseModel):
    reason: RevocationReason
    note: str | None = Field(default=None, max_length=300)


class BadgeOut(_Out):
    id: int
    employee_id: int
    version: int
    status: BadgeStatus
    issued_at: datetime
    expires_at: datetime | None
    revoked_at: datetime | None = None
    revoked_reason: RevocationReason | None = None
    revoked_note: str | None = None


class QrTokenOut(BaseModel):
    badge_id: int
    token: str


# --- zones ------------------------------------------------------------------
class UnitIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ZoneIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    antipassback_mode: AntiPassbackMode = AntiPassbackMode.DISABLED
    antipassback_warn_agent: bool = False
    unit_id: int | None = None  # omitted -> default unit
    code: str | None = Field(default=None, max_length=20)
    description: str | None = Field(default=None, max_length=500)
    sensitivity: ZoneSensitivity = ZoneSensitivity.STANDARD


class ZoneUpdateIn(BaseModel):
    """Partial edit; the control mode is changed by PATCH /zones/{id}/antipassback."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    code: str | None = Field(default=None, max_length=20)
    description: str | None = Field(default=None, max_length=500)
    sensitivity: ZoneSensitivity | None = None
    is_active: bool | None = None


class ZoneUnitIn(BaseModel):
    unit_id: int


class ZoneModeIn(BaseModel):
    antipassback_mode: AntiPassbackMode
    antipassback_warn_agent: bool | None = None  # omitted -> unchanged


class ZoneOut(_Out):
    id: int
    name: str
    code: str | None = None
    description: str | None = None
    sensitivity: ZoneSensitivity = ZoneSensitivity.STANDARD
    is_active: bool = True
    antipassback_mode: AntiPassbackMode
    antipassback_warn_agent: bool = False
    unit_id: int
    unit_name: str


class UnitOut(_Out):
    id: int
    name: str
    zones: list[ZoneOut]


class CheckpointIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    direction: Direction


class CheckpointUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    direction: Direction | None = None
    is_active: bool | None = None


class CheckpointOut(_Out):
    id: int
    name: str
    zone_id: int
    direction: Direction
    is_active: bool = True
    usable: bool = True  # post and zone both active
    zone_name: str
    unit_id: int
    unit_name: str
    agent_id: int | None
    agent_name: str | None  # agent currently posted here


class ScheduleIn(BaseModel):
    weekdays: list[int] = Field(min_length=1, max_length=7)  # 1 = lundi ... 7 = dimanche
    start: time
    end: time  # before start: the slot crosses midnight; equal: the whole day


class ScheduleOut(BaseModel):
    weekdays: list[int]
    start: time
    end: time


class RestrictionsIn(BaseModel):
    """All optional: nothing at all means a permanent access, 24 h / 24."""

    valid_from: AwareDatetime | None = None
    valid_until: AwareDatetime | None = None
    schedules: list[ScheduleIn] = Field(default_factory=list, max_length=10)


class AccessZoneOut(BaseModel):
    id: int
    name: str
    granted: bool
    is_active: bool = True
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    schedules: list[ScheduleOut] = Field(default_factory=list)
    restrictions: str = ""  # readable summary, empty when the access is permanent
    usable_now: bool = True  # False: ticked, but outside its dates / hours right now


class AccessUnitOut(BaseModel):
    unit_id: int
    unit_name: str
    status: str  # ACCES when at least one zone is ticked, REFUSE otherwise
    zones: list[AccessZoneOut]


class AccessIn(BaseModel):
    zone_ids: list[int]


class AuthorizationIn(BaseModel):
    employee_id: int
    zone_id: int
    valid_until: datetime | None = None


class AuthorizationOut(_Out):
    id: int
    employee_id: int
    zone_id: int
    valid_until: datetime | None


# --- scan -------------------------------------------------------------------
class ScanQrIn(BaseModel):
    checkpoint_id: int
    token: str


class ScanManualIn(BaseModel):
    checkpoint_id: int
    matricule: str


class ScannedEmployee(_Out):
    id: int
    matricule: str
    last_name: str
    first_name: str
    job_title: str | None
    department_name: str | None = None
    has_photo: bool = False
    photo_url: str | None = None  # signed, valid 60 s; None = "Photo absente"


class ScanOut(BaseModel):
    verdict: Verdict
    flags: list[Flag]
    occurred_at: datetime
    log_id: int
    direction: Direction
    zone: str
    checkpoint: str
    employee: ScannedEmployee | None
    # Shown to the agent as an orange banner (mode « Signalé » with the zone option on).
    warning: str | None = None
    # When the person was last recorded entering this zone (on « Déjà entré » and double entry).
    last_entry_at: datetime | None = None
    last_entry_checkpoint: str | None = None
    # Precise refusal for the agent: "Hors des horaires autorisés : lun–ven 07:00–18:00"...
    detail: str | None = None
    # Alert raised by this very scan (type code), announced by the phone. Never EMPLOYE_ARCHIVE:
    # the agent only sees « QR non reconnu » for an archived employee.
    alert: str | None = None


class UnblockIn(BaseModel):
    employee_id: int
    zone_id: int
    mode: UnblockMode = UnblockMode.EXIT
    reason: str = Field(min_length=3)


# --- journal ----------------------------------------------------------------
class LogOut(_Out):
    id: int
    occurred_at: datetime
    employee_id: int | None
    employee_name: str | None
    employee_matricule: str | None
    zone_id: int
    zone_name: str
    unit_id: int
    unit_name: str
    checkpoint_id: int
    checkpoint_name: str
    direction: Direction
    verdict: Verdict
    flags: list[str]
    operator_id: int | None
    device_id: int | None
    device_name: str | None
    agent_id: int | None
    agent_name: str | None
    reason: str | None
    method: ScanMethod = ScanMethod.QR


class PurgeIn(BaseModel):
    """Journal lines to delete: every filter given must match. ``before`` is exclusive."""
    date_from: AwareDatetime | None = None
    date_to: AwareDatetime | None = None
    before: AwareDatetime | None = None
    employee_id: int | None = None
    department_id: int | None = None
    entity_id: int | None = None
    zone_id: int | None = None
    dry_run: bool = False


class PhotoPurgeIn(BaseModel):
    """Photos to remove: a selection of employees and / or a department, an entity, archived only."""
    employee_ids: list[int] | None = Field(None, max_length=5000)
    department_id: int | None = None
    entity_id: int | None = None
    archived_only: bool = False
    dry_run: bool = False


class PurgeOut(BaseModel):
    deleted: int
    dry_run: bool = False
    filters: list[str] = []


class AuditOut(_Out):
    id: int
    occurred_at: datetime
    actor_id: int | None
    actor_name: str | None = None
    action: str
    target: str | None
    detail: dict
    ip: str | None = None

    @computed_field
    @property
    def action_label(self) -> str:
        return audit_label(self.action)

    @computed_field
    @property
    def summary(self) -> str:
        """Readable one-liner, the same as in the exports."""
        return describe_detail(self.detail)

    @computed_field
    @property
    def other(self) -> str:
        """The rest of the detail (motif, filters...), without before / after."""
        return describe_other(self.detail)

    @computed_field
    @property
    def changes(self) -> list[dict]:
        """Before / after, only the fields that changed."""
        return audit_changes(self.detail or {})


class AlertOut(_Out):
    id: int
    created_at: datetime
    type: AlertType
    status: AlertStatus
    message: str
    detail: dict
    badge_id: int | None
    employee_id: int | None
    access_log_id: int | None
    checkpoint_id: int | None
    handled_at: datetime | None
    note: str | None
    employee_name: str | None = None
    employee_matricule: str | None = None
    checkpoint_name: str | None = None
    zone_name: str | None = None


class AlertCountOut(BaseModel):
    new: int


class AlertAckIn(BaseModel):
    note: str | None = Field(default=None, max_length=300)


class AlertRevokeIn(BaseModel):
    reason: RevocationReason
    note: str | None = Field(default=None, max_length=300)


class TravelTimeIn(BaseModel):
    checkpoint_a_id: int
    checkpoint_b_id: int
    minutes: float = Field(ge=0, le=1440)


class TravelTimeOut(_Out):
    id: int
    checkpoint_a_id: int
    checkpoint_b_id: int
    min_seconds: int
    checkpoint_a_name: str | None = None
    checkpoint_b_name: str | None = None


class AuditActorOut(BaseModel):
    id: int
    name: str


# --- users & roles ------------------------------------------------------------
class UserIn(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    full_name: str
    password: str = Field(min_length=8, max_length=128)
    role_id: int


class OverrideOut(_Out):
    permission: str
    effect: OverrideEffect


class UserOut(_Out):
    id: int
    username: str
    full_name: str
    is_active: bool
    role_id: int
    overrides: list[OverrideOut]
    must_change_password: bool = False


class ActiveIn(BaseModel):
    is_active: bool


class RoleAssignIn(BaseModel):
    role_id: int


class OverrideIn(BaseModel):
    permission: Permission
    effect: OverrideEffect


class RoleOut(_Out):
    id: int
    name: str
    label: str
    permissions: list[str]


class RoleUpdateIn(BaseModel):
    permissions: list[Permission]


# --- import -------------------------------------------------------------------
class RejectedRow(BaseModel):
    row: int
    matricule: str | None
    errors: list[str]


class BulkIn(BaseModel):
    """Who: ``employee_ids``, or everybody on staff ``in_department_id`` / ``in_entity_id``.
    What: ``action``; for « org », only the fields sent are changed (``null`` clears it)."""

    action: BulkAction
    employee_ids: list[int] | None = Field(default=None, max_length=1000)
    in_department_id: int | None = None
    in_entity_id: int | None = None
    entity_id: int | None = None
    department_id: int | None = None
    zone_ids: list[int] | None = Field(default=None, max_length=200)
    reason: str | None = Field(default=None, max_length=300)
    dry_run: bool = False  # only count the employees concerned


class BulkFailureOut(BaseModel):
    employee_id: int
    matricule: str
    reason: str


class BulkOut(BaseModel):
    action: BulkAction
    dry_run: bool
    target: str
    total: int
    done: int
    unchanged: int
    failed: list[BulkFailureOut]


class ImportPreviewRow(BaseModel):
    row: int
    matricule: str
    last_name: str
    first_name: str
    entity: str | None = None
    department: str | None = None
    job_title: str | None = None


class ImportCheckOut(BaseModel):
    """Step 1 of the import: what would be created, nothing written yet."""

    file_name: str | None
    total: int
    valid: int
    rejected: list[RejectedRow]
    new_entities: list[str]
    new_departments: list[str]
    preview: list[ImportPreviewRow]  # the first conforming rows


class ImportReport(BaseModel):
    created: int
    rejected: list[RejectedRow]
    created_entities: list[str]
    created_departments: list[str]


# --- reference data, presence, dashboard ------------------------------------------
class EntityOut(_Out):
    id: int
    name: str


class DepartmentOut(_Out):
    id: int
    name: str


class NameIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class OrgItemOut(BaseModel):
    id: int
    name: str
    employees: int = 0  # employees using it, archived included


class OrgOut(BaseModel):
    entities: list[OrgItemOut]
    departments: list[OrgItemOut]


class PresenceOut(BaseModel):
    employee_id: int
    matricule: str
    full_name: str
    zone_id: int
    zone_name: str
    entered_at: datetime


class StatsOut(BaseModel):
    since: datetime
    total: int
    entries_authorized: int
    exits: int
    refused: int
    inside: int
    by_verdict: dict[str, int]


# --- devices (phones paired for scanning) ------------------------------------------
class DeviceIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class DeviceOut(_Out):
    id: int
    name: str
    status: str
    created_at: datetime
    paired_at: datetime | None
    last_seen_at: datetime | None
    revoked_at: datetime | None
    code_expires_at: datetime | None
    voice_enabled: bool = True
    current_post: str | None = None
    checkpoint_since: datetime | None = None
    scope_summary: str = "Tout le site"
    scope_ids: dict = Field(default_factory=lambda: {"unit_ids": [], "zone_ids": [], "checkpoint_ids": []})


class DeviceVoiceIn(BaseModel):
    enabled: bool


class DevicePostIn(BaseModel):
    checkpoint_id: int


class DevicePostOut(BaseModel):
    checkpoint_id: int
    current_post: str
    since: datetime


class DeviceScanOut(BaseModel):
    """One line of the phone's history: time, person, result. No photo, no internal reason."""

    id: int
    occurred_at: datetime
    checkpoint_name: str
    zone_name: str
    direction: Direction
    verdict: Verdict
    method: ScanMethod
    flags: list[str]
    employee_name: str | None
    employee_matricule: str | None


class DeviceSettingsOut(BaseModel):
    """What a paired phone needs to know about itself."""

    name: str
    voice_enabled: bool


class DeviceScopeIn(BaseModel):
    """All empty: the phone covers the whole site."""

    unit_ids: list[int] = Field(default_factory=list)
    zone_ids: list[int] = Field(default_factory=list)
    checkpoint_ids: list[int] = Field(default_factory=list)


class DeviceCodeOut(BaseModel):
    device: DeviceOut
    code: str


class PairIn(BaseModel):
    code: str = Field(min_length=4, max_length=20)


class PairOut(BaseModel):
    device_token: str
    device_name: str


# --- agents -------------------------------------------------------------------------
class AgentIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    matricule: str | None = Field(default=None, max_length=40)


class AgentPostOut(BaseModel):
    checkpoint_id: int
    checkpoint_name: str
    direction: Direction
    zone_name: str
    unit_name: str
    since: datetime


class AgentOut(_Out):
    id: int
    full_name: str
    matricule: str | None
    is_active: bool
    posts: list[AgentPostOut] = []  # every post currently held (entry + exit of one door...)
    # First post, kept for older screens.
    checkpoint_id: int | None = None
    checkpoint_name: str | None = None
    zone_name: str | None = None
    unit_name: str | None = None


class AssignIn(BaseModel):
    agent_id: int | None  # null empties the post
    keep_other_posts: bool = False  # True: the agent also keeps the posts already held


class AssignmentOut(_Out):
    id: int
    agent_id: int
    agent_name: str
    checkpoint_id: int
    checkpoint_name: str
    zone_name: str
    unit_name: str
    started_at: datetime
    ended_at: datetime | None


# --- live supervision (tableau de bord) ----------------------------------------------
class MonitorPerson(BaseModel):
    employee_id: int
    full_name: str
    matricule: str
    department_name: str | None
    at: datetime  # entered at (inside) / left at (exited)
    checkpoint_name: str | None


class MonitorZone(BaseModel):
    zone_id: int
    zone_name: str
    code: str | None
    mode: AntiPassbackMode
    is_active: bool
    inside: int
    exited: int
    entries: int
    exits: int
    refused: int
    anomalies: int
    last_activity: datetime | None
    people_inside: list[MonitorPerson]
    people_exited: list[MonitorPerson]


class MonitorUnit(BaseModel):
    unit_id: int
    unit_name: str
    inside: int
    exited: int
    entries: int
    exits: int
    refused: int
    anomalies: int
    zones: list[MonitorZone]


class MonitorPost(BaseModel):
    checkpoint_id: int
    checkpoint_name: str
    direction: Direction
    zone_name: str
    unit_name: str
    usable: bool
    agent_name: str | None
    scans_today: int
    last_scan: datetime | None


class MonitorRefusal(BaseModel):
    log_id: int
    at: datetime
    verdict: Verdict
    employee_name: str | None
    matricule: str | None
    zone_name: str
    checkpoint_name: str
    agent_name: str | None
    reason: str | None


class MonitorTotals(BaseModel):
    entries: int
    exits: int
    refused: int
    unknown_qr: int
    anomalies: int
    inside: int
    exited: int
    flags: dict[str, int]


class MonitoringOut(BaseModel):
    generated_at: datetime
    since: datetime
    totals: MonitorTotals
    units: list[MonitorUnit]
    posts: list[MonitorPost]
    recent_refusals: list[MonitorRefusal]


# --- reports over a period (tâche 32) ---------------------------------------------------------
class MovementRowOut(_Out):
    employee_id: int
    matricule: str
    full_name: str
    entity_name: str | None
    department_name: str | None
    unit_name: str
    zone_id: int
    zone_name: str
    entries: int
    exits: int
    refused: int
    unblocks: int
    first_at: datetime
    last_at: datetime


class MovementReportOut(_Out):
    rows: list[MovementRowOut]
    employees: int
    entries: int
    exits: int
    refused: int
    unblocks: int


class ZonePresenceRowOut(_Out):
    unit_name: str
    zone_id: int
    zone_name: str
    mode: AntiPassbackMode
    inside_now: int | None = Field(description="Personnes à l'intérieur maintenant ; null pour une zone « Libre »")
    people: int
    entries: int
    exits: int
    refused: int


class PresenceReportOut(_Out):
    rows: list[ZonePresenceRowOut]
    inside_now: int
    entries: int
    exits: int
    refused: int


class TrendDayOut(_Out):
    day: date
    total: int
    by_verdict: dict[str, int]


class CountByZoneOut(_Out):
    zone_id: int
    zone_name: str
    unit_name: str
    count: int


class CountByEmployeeOut(_Out):
    employee_id: int
    matricule: str
    full_name: str
    count: int


class RefusalTrendOut(_Out):
    date_from: datetime
    date_to: datetime
    total: int
    previous_total: int
    days: list[TrendDayOut]
    by_verdict: dict[str, int]
    by_zone: list[CountByZoneOut]
    by_employee: list[CountByEmployeeOut]
    unknown_qr: int
