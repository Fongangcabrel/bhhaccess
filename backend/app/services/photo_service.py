"""Employee photos: normalised on upload, stored on disk, served through short-lived signed URLs.

* Upload: JPEG or PNG, 2 MB max. The server re-encodes the image: EXIF orientation applied,
  every metadata dropped (location, device...), centred 3:4 portrait crop, 600 x 800 JPEG.
* Reading: an <img> tag cannot send a bearer token, so the API hands out a URL signed with
  HMAC that expires after 60 s (TRD §8, NFR-05). The signature covers the file name, so an old
  URL dies as soon as the photo is replaced or removed.
"""
import hashlib
import hmac
import secrets
from datetime import timedelta
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.clock import Clock
from app.core.exceptions import DomainError, NotFoundError
from app.domain.enums import EmployeeStatus
from app.models import Employee
from app.repositories.repositories import EmployeeRepository
from app.services.audit_service import AuditService

ACCEPTED_FORMATS = {"JPEG", "PNG"}
MAX_PIXELS = 40_000_000  # refuse decompression bombs before decoding
PORTRAIT = (600, 800)  # width x height, 3:4
URL_TTL = timedelta(seconds=60)


def normalise_photo(content: bytes, max_bytes: int) -> bytes:
    """Return a clean portrait JPEG, or raise DomainError with a message for the user."""
    if not content:
        raise DomainError("Fichier vide")
    if len(content) > max_bytes:
        raise DomainError(f"Photo trop lourde : {max_bytes // (1024 * 1024)} Mo maximum")
    try:
        with Image.open(BytesIO(content)) as probe:
            if probe.format not in ACCEPTED_FORMATS:
                raise DomainError("Format refusé : JPEG ou PNG uniquement")
            if probe.width * probe.height > MAX_PIXELS:
                raise DomainError("Image trop grande")
            probe.verify()
        with Image.open(BytesIO(content)) as image:
            image = ImageOps.exif_transpose(image)  # phones store the rotation in EXIF
            if image.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGB", image.size, (255, 255, 255))
                rgba = image.convert("RGBA")
                background.paste(rgba, mask=rgba.split()[-1])
                image = background
            portrait = ImageOps.fit(image.convert("RGB"), PORTRAIT, method=Image.Resampling.LANCZOS,
                                    centering=(0.5, 0.4))  # keep the face, slightly above centre
    except DomainError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise DomainError("Image illisible : envoyez une photo JPEG ou PNG") from exc
    out = BytesIO()
    portrait.save(out, format="JPEG", quality=85, optimize=True)  # a fresh file carries no EXIF
    return out.getvalue()


class PhotoUrlSigner:
    def __init__(self, secret: str, clock: Clock) -> None:
        # Own key, derived from the session secret: a photo URL can never be used as anything else.
        self._key = hashlib.sha256(b"bhhaccess-photo-url:" + secret.encode()).digest()
        self._clock = clock

    def _sign(self, employee_id: int, photo_path: str, expires: int) -> str:
        message = f"{employee_id}|{photo_path}|{expires}".encode()
        return hmac.new(self._key, message, hashlib.sha256).hexdigest()[:32]

    def url_for(self, employee: Employee) -> str | None:
        if not employee.photo_path:
            return None
        expires = int((self._clock.now() + URL_TTL).timestamp())
        sig = self._sign(employee.id, employee.photo_path, expires)
        return f"/api/photos/{employee.id}?exp={expires}&sig={sig}"

    def check(self, employee: Employee, expires: int, sig: str) -> bool:
        if not employee.photo_path or expires < self._clock.now().timestamp():
            return False
        return hmac.compare_digest(sig, self._sign(employee.id, employee.photo_path, expires))


class PhotoService:
    def __init__(self, employees: EmployeeRepository, audit: AuditService, directory: str, max_bytes: int) -> None:
        self._employees = employees
        self._audit = audit
        self._dir = Path(directory)
        self._max = max_bytes

    def upload(self, actor_id: int, employee_id: int, content: bytes) -> Employee:
        employee = self._require(employee_id)
        if employee.status == EmployeeStatus.ARCHIVED:
            raise DomainError("Employé archivé : restaurez-le avant de changer sa photo")
        jpeg = normalise_photo(content, self._max)
        self._dir.mkdir(parents=True, exist_ok=True)
        name = f"{employee.id}-{secrets.token_hex(8)}.jpg"  # unguessable, and a new name per version
        (self._dir / name).write_bytes(jpeg)
        old, employee.photo_path = employee.photo_path, name
        self._employees.flush()
        self._delete_file(old)
        self._audit.record(actor_id, "employee.photo", employee.matricule, previous_photo=old is not None)
        return employee

    def remove(self, actor_id: int, employee_id: int) -> Employee:
        employee = self._require(employee_id)
        if not employee.photo_path:
            raise NotFoundError("Cet employé n'a pas de photo")
        old, employee.photo_path = employee.photo_path, None
        self._employees.flush()
        self._delete_file(old)
        self._audit.record(actor_id, "employee.photo.delete", employee.matricule)
        return employee

    def read(self, employee: Employee) -> bytes:
        path = self._file(employee.photo_path)
        if path is None or not path.is_file():
            raise NotFoundError("Photo introuvable")
        return path.read_bytes()

    def _file(self, name: str | None) -> Path | None:
        if not name or "/" in name or "\\" in name or name.startswith("."):
            return None  # names are always generated by upload(); refuse anything else
        return self._dir / name

    def _delete_file(self, name: str | None) -> None:
        path = self._file(name)
        if path is not None:
            path.unlink(missing_ok=True)

    def _require(self, employee_id: int) -> Employee:
        employee = self._employees.get(employee_id)
        if employee is None:
            raise NotFoundError("Employé introuvable")
        return employee
