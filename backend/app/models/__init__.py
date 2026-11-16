"""Importing the package registers every table on ``Base.metadata``."""
from app.models.agent import Agent, AgentAssignment
from app.models.alert import Alert, TravelTime
from app.models.badge import Badge
from app.models.device import Device, DeviceScope
from app.models.employee import Employee
from app.models.journal import AccessLog, AuditEntry
from app.models.organization import Department, Entity
from app.models.user import Role, User, UserPermissionOverride
from app.models.zone import AccessSchedule, Checkpoint, Unit, Zone, ZoneAuthorization, ZonePresence

__all__ = [
    "AccessLog", "AccessSchedule", "Agent", "Alert", "TravelTime",
    "AgentAssignment", "AuditEntry", "Badge", "Checkpoint", "Department",
    "Device", "DeviceScope", "Employee", "Entity", "Role", "Unit", "User", "UserPermissionOverride", "Zone",
    "ZoneAuthorization", "ZonePresence",
]
