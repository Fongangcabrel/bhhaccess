"""Business vocabulary shared by every layer."""
from enum import StrEnum


class EmployeeStatus(StrEnum):
    ACTIVE = "ACTIF"
    SUSPENDED = "SUSPENDU"
    ARCHIVED = "ARCHIVE"


class BadgeStatus(StrEnum):
    ACTIVE = "ACTIF"
    REVOKED = "REVOQUE"


class RevocationReason(StrEnum):
    """Why a badge stopped working (SRS FR-52, Backend Schema « badges.revoked_reason »)."""

    LOST = "PERTE"
    STOLEN = "VOL"
    DEPARTURE = "DEPART"
    REPLACED = "REMPLACEMENT"
    OTHER = "AUTRE"


class AntiPassbackMode(StrEnum):
    DISABLED = "DESACTIVE"
    SOFT = "SOUPLE"
    STRICT = "STRICT"


class ZoneSensitivity(StrEnum):
    """Information only (SRS FR-30): access is always decided by the explicit authorisations."""

    STANDARD = "STANDARD"
    RESTRICTED = "RESTREINTE"
    CRITICAL = "CRITIQUE"


class Direction(StrEnum):
    ENTRY = "ENTREE"
    EXIT = "SORTIE"


class Verdict(StrEnum):
    AUTHORIZED = "AUTORISE"
    DENIED_ZONE = "REFUSE_ZONE"
    DENIED_REVOKED = "REFUSE_REVOQUE"
    DENIED_EXPIRED = "REFUSE_EXPIRE"
    DENIED_EMPLOYEE_INACTIVE = "REFUSE_EMPLOYE_INACTIF"
    DENIED_INVALID = "REFUSE_INVALIDE"
    DENIED_ANTIPASSBACK = "REFUSE_ANTIPASSBACK"
    EXIT_RECORDED = "SORTIE_ENREGISTREE"


class Flag(StrEnum):
    EXIT_BADGE_REVOKED = "SORTIE_BADGE_REVOQUE"
    EXIT_BADGE_EXPIRED = "SORTIE_BADGE_EXPIRE"
    EXIT_EMPLOYEE_SUSPENDED = "SORTIE_EMPLOYE_SUSPENDU"
    DOUBLE_ENTRY = "DOUBLE_ENTREE"
    EXIT_WITHOUT_ENTRY = "SORTIE_SANS_ENTREE"
    UNBLOCKED = "DEBLOQUE"


class ScanMethod(StrEnum):
    """How a journal line was produced (Backend Schema access_logs.method)."""

    QR = "QR"
    MANUAL = "MANUEL"  # matricule typed by the agent (damaged QR)
    CONSOLE = "CONSOLE"  # manual unblock from the console: not a scan


class AlertType(StrEnum):
    """Suspicious use of a badge (SRS FR-90 to FR-92)."""

    SIMULTANEOUS = "SIMULTANEE"  # two posts faster than the walking time between them
    REVOKED_USE = "BADGE_REVOQUE"  # revoked or replaced badge presented
    ARCHIVED_USE = "EMPLOYE_ARCHIVE"  # QR of an archived employee presented
    OUTSIDE_HOURS = "HORS_HORAIRE"  # entry tried outside the allowed slots
    BURST = "RAFALE"  # many scans of one badge in a short time
    REPEATED_REFUSALS = "REFUS_REPETES"  # several refusals for one badge in a short time


class AlertStatus(StrEnum):
    NEW = "NOUVELLE"
    ACKNOWLEDGED = "PRISE_EN_COMPTE"


class OverrideEffect(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


class BulkAction(StrEnum):
    """Same change for many employees (SRS FR-28, FR-42)."""

    ORG = "org"  # entity and/or department
    SUSPEND = "suspend"
    REACTIVATE = "reactivate"
    ARCHIVE = "archive"
    ADD_ZONES = "add_zones"
    REMOVE_ZONES = "remove_zones"
