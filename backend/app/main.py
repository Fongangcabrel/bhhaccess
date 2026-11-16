"""Application factory: builds the FastAPI app and wires shared infrastructure."""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

import app.models  # noqa: F401  (registers tables)
from app import api_docs
from app.controllers import (
    admin_controller,
    agent_controller,
    alert_controller,
    auth_controller,
    badge_controller,
    device_controller,
    employee_controller,
    export_controller,
    journal_controller,
    org_controller,
    photo_controller,
    scan_controller,
    user_controller,
    zone_controller,
)
from app.core.clock import Clock, SystemClock
from app.core.config import Settings, get_settings
from app.core.database import Base, build_engine, build_session_factory
from app.core.exceptions import DomainError
from app.core.i18n import request_lang, tr
from app.core.rate_limit import FailureLimiter
from app.core.security import SessionTokenCodec
from app.domain.qr_token import Ed25519TokenSigner, load_or_create_dev_key
from app.domain.rules import build_default_engine
from app.services.alert_service import AlertRules
from app.services.bootstrap import seed_defaults
from app.services.photo_service import PhotoUrlSigner
from app.services.qr_image import QrImageRenderer


def create_app(settings: Settings | None = None, clock: Clock | None = None) -> FastAPI:
    settings = settings or get_settings()
    clock = clock or SystemClock()

    engine = build_engine(settings.database_url)
    if settings.database_url.startswith("sqlite"):
        Base.metadata.create_all(engine)  # dev/tests only; PostgreSQL schemas are managed by Alembic
    session_factory = build_session_factory(engine)
    with session_factory() as session:
        seed_defaults(session, settings)

    app = FastAPI(title="BHHaccess", version="0.1.0")
    app.state.session_factory = session_factory
    app.state.clock = clock
    app.state.timezone = settings.timezone
    app.state.trust_proxy_headers = settings.trust_proxy_headers
    app.state.alert_rules = AlertRules(
        default_seconds_between_units=settings.alert_default_seconds_between_units,
        burst_count=settings.alert_burst_count, burst_seconds=settings.alert_burst_seconds,
        refusal_count=settings.alert_refusal_count, refusal_minutes=settings.alert_refusal_minutes,
    )
    qr_key = settings.qr_private_key_pem or load_or_create_dev_key(settings.qr_dev_key_path)
    app.state.signer = Ed25519TokenSigner(qr_key, settings.qr_issuer)
    app.state.engine = build_default_engine()
    app.state.qr_renderer = QrImageRenderer(settings.qr_logo_path)
    app.state.pairing_limiter = FailureLimiter(clock)
    app.state.codec = SessionTokenCodec(settings.jwt_secret, settings.access_token_minutes, clock)
    app.state.photo_signer = PhotoUrlSigner(settings.jwt_secret, clock)
    app.state.photos_dir = settings.photos_dir
    app.state.qr_logo_path = settings.qr_logo_path
    app.state.photo_max_bytes = settings.photo_max_bytes
    app.state.import_max_bytes = settings.import_max_bytes

    @app.exception_handler(DomainError)
    async def handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": tr(exc.message, request_lang(request))})

    for module in (auth_controller, employee_controller, badge_controller,
                   zone_controller, scan_controller, journal_controller, user_controller, admin_controller,
                   device_controller, agent_controller, photo_controller, export_controller, org_controller,
                   alert_controller):
        app.include_router(module.router, prefix="/api")

    @app.get("/health", tags=["ops"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    api_docs.apply(app)  # /docs: French sections, summaries and required rights
    return app
