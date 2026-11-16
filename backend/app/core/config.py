"""Application settings, loaded from environment variables (prefix ``BHH_``)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BHH_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./bhhaccess.db"
    # Behind Nginx: read the client IP from X-Forwarded-For (audit). Leave false when exposed directly.
    trust_proxy_headers: bool = False
    jwt_secret: str = "change-me-in-production"
    access_token_minutes: int = 480
    timezone: str = "Africa/Douala"  # reports and exports display local time

    # Ed25519 private key (PEM) used to sign badge QR tokens.
    # When empty, a local dev key file is created and reused (development only).
    qr_private_key_pem: str = ""
    qr_dev_key_path: str = ".qr_dev_key.pem"  # used only when qr_private_key_pem is empty
    qr_issuer: str = "bhhaccess"
    qr_logo_path: str = "assets/logo.png"

    photos_dir: str = "data/photos"  # Docker: a dedicated volume mounted at /data/photos
    photo_max_bytes: int = 2 * 1024 * 1024
    import_max_bytes: int = 5 * 1024 * 1024  # Excel import

    # Suspicious use (alerts): default walking time between two different units, bursts, refusals.
    alert_default_seconds_between_units: int = 600
    alert_burst_count: int = 5
    alert_burst_seconds: int = 60
    alert_refusal_count: int = 3
    alert_refusal_minutes: int = 10

    initial_admin_username: str = "admin"
    initial_admin_password: str = "admin-change-me"
    initial_admin_must_change_password: bool = True  # the installation password is temporary


@lru_cache
def get_settings() -> Settings:
    return Settings()
