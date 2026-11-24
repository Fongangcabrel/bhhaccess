"""Composition root: wires repositories -> services for each request (dependency injection).

Controllers depend on these providers, never on concrete construction, so tests can
override any of them.
"""
from collections.abc import Callable, Iterator

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.database import session_scope
from app.core.exceptions import AuthenticationError, ForbiddenError
from app.core.net import client_ip
from app.core.rate_limit import FailureLimiter
from app.core.security import SessionTokenCodec
from app.domain.permissions import Permission
from app.domain.qr_token import TokenSigner
from app.domain.rules import DecisionEngine
from app.models import User
from app.repositories import repositories as r
from app.services.agent_service import AgentService
from app.services.alert_service import AlertService
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService
from app.services.badge_service import BadgeService
from app.services.bulk_service import BulkService
from app.services.device_service import DeviceService
from app.services.employee_service import EmployeeService
from app.services.import_service import EmployeeImportService
from app.services.journal_service import JournalService
from app.services.monitoring_service import MonitoringService
from app.services.org_service import OrgService
from app.services.period_report_service import PeriodReportService
from app.services.permission_service import PermissionService
from app.services.photo_service import PhotoService, PhotoUrlSigner
from app.services.presence_service import PresenceService
from app.services.qr_image import QrImageRenderer
from app.services.report_service import ReportService
from app.services.scan_service import ScanService
from app.services.settings_service import SettingsService
from app.services.user_service import UserService
from app.services.zone_service import ZoneService

_bearer = HTTPBearer(auto_error=False)


def get_session(request: Request) -> Iterator[Session]:
    yield from session_scope(request.app.state.session_factory)


def get_clock(request: Request) -> Clock:
    return request.app.state.clock


def get_signer(request: Request) -> TokenSigner:
    return request.app.state.signer


def get_qr_renderer(request: Request) -> QrImageRenderer:
    return request.app.state.qr_renderer


def get_engine(request: Request) -> DecisionEngine:
    return request.app.state.engine


def get_codec(request: Request) -> SessionTokenCodec:
    return request.app.state.codec


def get_photo_signer(request: Request) -> PhotoUrlSigner:
    return request.app.state.photo_signer


def get_audit(request: Request, session: Session = Depends(get_session),
              clock: Clock = Depends(get_clock)) -> AuditService:
    """Every audit line carries the caller's IP (Backend Schema, audit_logs.ip)."""
    ip = client_ip(request, getattr(request.app.state, "trust_proxy_headers", False))
    return AuditService(r.AuditRepository(session), clock, ip, r.UserRepository(session))


def get_settings_service(request: Request, session: Session = Depends(get_session), clock: Clock = Depends(get_clock),
                         audit: AuditService = Depends(get_audit)) -> SettingsService:
    return SettingsService(session, request.app.state.setting_defaults, clock, audit)


def get_auth_service(session: Session = Depends(get_session), codec: SessionTokenCodec = Depends(get_codec),
                     clock: Clock = Depends(get_clock), audit: AuditService = Depends(get_audit),
                     settings: SettingsService = Depends(get_settings_service)) -> AuthService:
    return AuthService(r.UserRepository(session), codec, audit, clock, r.RefreshTokenRepository(session), settings)


def get_employee_service(session: Session = Depends(get_session), audit: AuditService = Depends(get_audit),
                         clock: Clock = Depends(get_clock)) -> EmployeeService:
    return EmployeeService(r.EmployeeRepository(session), r.BadgeRepository(session),
                           r.PresenceRepository(session), audit, clock, OrgService(session, audit))


def get_badge_service(session: Session = Depends(get_session), signer: TokenSigner = Depends(get_signer),
                      audit: AuditService = Depends(get_audit), clock: Clock = Depends(get_clock)) -> BadgeService:
    return BadgeService(r.BadgeRepository(session), r.EmployeeRepository(session), signer, audit, clock)


def get_zone_service(session: Session = Depends(get_session), audit: AuditService = Depends(get_audit),
                     clock: Clock = Depends(get_clock),
                     request: Request = None) -> ZoneService:  # type: ignore[assignment]  (FastAPI fills it)
    timezone = request.app.state.timezone if request is not None else "Africa/Douala"
    return ZoneService(r.ZoneRepository(session), r.CheckpointRepository(session),
                       r.AuthorizationRepository(session), r.EmployeeRepository(session),
                       r.UnitRepository(session), audit, r.AccessLogRepository(session),
                       r.AssignmentRepository(session), r.PresenceRepository(session), clock, timezone)


def get_scan_service(session: Session = Depends(get_session), signer: TokenSigner = Depends(get_signer),
                     engine: DecisionEngine = Depends(get_engine), clock: Clock = Depends(get_clock),
                     request: Request = None) -> ScanService:  # type: ignore[assignment]  (FastAPI fills it)
    return ScanService(
        badges=r.BadgeRepository(session), employees=r.EmployeeRepository(session),
        checkpoints=r.CheckpointRepository(session), zones=r.ZoneRepository(session),
        authorizations=r.AuthorizationRepository(session), presences=r.PresenceRepository(session),
        logs=r.AccessLogRepository(session), assignments=r.AssignmentRepository(session),
        signer=signer, engine=engine, clock=clock, timezone=request.app.state.timezone,
        alerts=AlertService(session, None, clock,
                            SettingsService(session, request.app.state.setting_defaults, clock).alert_rules()),
    )


def get_presence_service(session: Session = Depends(get_session), audit: AuditService = Depends(get_audit),
                         clock: Clock = Depends(get_clock)) -> PresenceService:
    return PresenceService(r.PresenceRepository(session), r.EmployeeRepository(session),
                           r.ZoneRepository(session), r.CheckpointRepository(session),
                           r.AccessLogRepository(session), audit, clock)


def get_device_service(request: Request, session: Session = Depends(get_session),
                       audit: AuditService = Depends(get_audit), clock: Clock = Depends(get_clock)) -> DeviceService:
    limiter: FailureLimiter = request.app.state.pairing_limiter
    return DeviceService(r.DeviceRepository(session), audit, clock, limiter, r.AccessLogRepository(session),
                         r.UnitRepository(session), r.ZoneRepository(session), r.CheckpointRepository(session))


def get_agent_service(session: Session = Depends(get_session), audit: AuditService = Depends(get_audit),
                      clock: Clock = Depends(get_clock)) -> AgentService:
    return AgentService(r.AgentRepository(session), r.AssignmentRepository(session),
                        r.CheckpointRepository(session), audit, clock, r.AccessLogRepository(session))


def get_journal_service(session: Session = Depends(get_session),
                        audit: AuditService = Depends(get_audit)) -> JournalService:
    return JournalService(r.AccessLogRepository(session), audit)


def get_user_service(session: Session = Depends(get_session), audit: AuditService = Depends(get_audit),
                     clock: Clock = Depends(get_clock)) -> UserService:
    return UserService(r.UserRepository(session), r.RoleRepository(session), audit, clock)


def get_import_service(session: Session = Depends(get_session),
                       audit: AuditService = Depends(get_audit)) -> EmployeeImportService:
    return EmployeeImportService(r.EmployeeRepository(session), r.EntityRepository(session),
                                 r.DepartmentRepository(session), audit)


def get_period_report_service(request: Request, session: Session = Depends(get_session),
                              clock: Clock = Depends(get_clock)) -> PeriodReportService:
    return PeriodReportService(r.AccessLogRepository(session), r.PresenceRepository(session),
                               r.EmployeeRepository(session), r.ZoneRepository(session), clock,
                               request.app.state.timezone)


def get_report_service(request: Request, session: Session = Depends(get_session),
                       clock: Clock = Depends(get_clock)) -> ReportService:
    return ReportService(r.AccessLogRepository(session), r.PresenceRepository(session), clock,
                         request.app.state.timezone)


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
                     auth: AuthService = Depends(get_auth_service)) -> User:
    if credentials is None:
        raise AuthenticationError("Authentification requise")
    return auth.authenticate(credentials.credentials)


def require(permission: Permission) -> Callable[..., User]:
    """Route guard: ``Depends(require(Permission.LOGS_VIEW))`` returns the authorised user."""

    def guard(user: User = Depends(get_current_user)) -> User:
        if user.must_change_password:
            # Only /auth/me and /auth/password (which use get_current_user directly) stay open.
            raise ForbiddenError("Changez votre mot de passe temporaire avant de continuer")
        PermissionService().require(user, permission)
        return user

    guard.permissions = (permission,)  # read by app.api_docs (« Droit requis » in /docs)
    return guard


def get_photo_service(request: Request, session: Session = Depends(get_session),
                      audit: AuditService = Depends(get_audit)) -> PhotoService:
    return PhotoService(r.EmployeeRepository(session), audit, request.app.state.photos_dir,
                        request.app.state.photo_max_bytes)


def get_monitoring_service(request: Request, session: Session = Depends(get_session),
                           clock: Clock = Depends(get_clock)) -> MonitoringService:
    return MonitoringService(r.AccessLogRepository(session), r.PresenceRepository(session),
                             r.UnitRepository(session), r.CheckpointRepository(session), clock,
                             request.app.state.timezone)


def require_all(*permissions: Permission) -> Callable[..., User]:
    """Route guard needing several rights, e.g. exporting the journal = logs.view + data.export."""

    def guard(user: User = Depends(require(permissions[0]))) -> User:
        for permission in permissions[1:]:
            PermissionService().require(user, permission)
        return user

    guard.permissions = permissions
    return guard


def get_bulk_service(session: Session = Depends(get_session), audit: AuditService = Depends(get_audit),
                     employees: EmployeeService = Depends(get_employee_service),
                     zones: ZoneService = Depends(get_zone_service)) -> BulkService:
    return BulkService(session, employees, zones, audit)


def get_org_service(session: Session = Depends(get_session), audit: AuditService = Depends(get_audit)) -> OrgService:
    return OrgService(session, audit)


def get_alert_service(request: Request, session: Session = Depends(get_session),
                      audit: AuditService = Depends(get_audit), clock: Clock = Depends(get_clock)) -> AlertService:
    rules = SettingsService(session, request.app.state.setting_defaults, clock).alert_rules()
    return AlertService(session, audit, clock, rules)
