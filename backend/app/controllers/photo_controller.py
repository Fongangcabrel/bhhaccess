"""Employee photos: upload / remove (back-office) and reading through a signed, short-lived URL."""
from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile

from app.controllers.deps import get_photo_service, get_photo_signer, get_session, require
from app.core.exceptions import DomainError, NotFoundError
from app.domain.permissions import Permission
from app.models import Department, Employee, Entity, User
from app.repositories.repositories import EmployeeRepository
from app.schemas.dto import EmployeeOut, PhotoPurgeIn, PurgeOut
from app.services.photo_service import PhotoService, PhotoUrlSigner

router = APIRouter(tags=["photos"])


def employee_out(employee: Employee, signer: PhotoUrlSigner) -> EmployeeOut:
    """EmployeeOut with a fresh signed photo URL (an <img> tag cannot send the bearer token)."""
    return EmployeeOut.model_validate(employee).model_copy(update={"photo_url": signer.url_for(employee)})


@router.post("/employees/{employee_id}/photo", response_model=EmployeeOut)
async def upload_photo(employee_id: int, request: Request, file: UploadFile = File(...),
                       actor: User = Depends(require(Permission.EMPLOYEES_EDIT)),
                       service: PhotoService = Depends(get_photo_service),
                       signer: PhotoUrlSigner = Depends(get_photo_signer)):
    limit = request.app.state.photo_max_bytes
    content = await file.read(limit + 1)  # never hold more than the limit in memory
    if len(content) > limit:
        raise DomainError(f"Photo trop lourde : {limit // (1024 * 1024)} Mo maximum")
    return employee_out(service.upload(actor.id, employee_id, content), signer)


@router.delete("/employees/{employee_id}/photo", response_model=EmployeeOut)
def delete_photo(employee_id: int, actor: User = Depends(require(Permission.EMPLOYEES_EDIT)),
                 service: PhotoService = Depends(get_photo_service),
                 signer: PhotoUrlSigner = Depends(get_photo_signer)):
    return employee_out(service.remove(actor.id, employee_id), signer)


@router.get("/photos/{employee_id}", response_class=Response, include_in_schema=False)
def read_photo(employee_id: int, exp: int = Query(...), sig: str = Query(..., max_length=64),
               session=Depends(get_session), service: PhotoService = Depends(get_photo_service),
               signer: PhotoUrlSigner = Depends(get_photo_signer)):
    """No login here: the signature, bound to the file and valid 60 s, is the authorisation."""
    employee = session.get(Employee, employee_id)
    if employee is None or not signer.check(employee, exp, sig):
        raise NotFoundError("Photo introuvable ou lien expiré")
    return Response(content=service.read(employee), media_type="image/jpeg",
                    headers={"Cache-Control": "private, max-age=60", "X-Content-Type-Options": "nosniff"})


@router.post("/photos/purge", response_model=PurgeOut)
def purge_photos(body: PhotoPurgeIn, actor: User = Depends(require(Permission.DATA_PURGE)),
                 session=Depends(get_session), service: PhotoService = Depends(get_photo_service)):
    """Bulk removal of photos (FR-97/98). ``dry_run`` gives the number of photos first."""
    nothing = body.employee_ids is None and body.department_id is None and body.entity_id is None
    if nothing and not body.archived_only:
        raise DomainError("Choisissez au moins un filtre (sélection, département, entité ou archivés)")
    described = []
    if body.employee_ids is not None:
        described.append(f"{len(body.employee_ids)} employé(s) sélectionné(s)")
    for model, value, label, missing in (
        (Entity, body.entity_id, "Entité", "Entité introuvable"),
        (Department, body.department_id, "Département", "Département introuvable"),
    ):
        if value is not None:
            item = session.get(model, value)
            if item is None:
                raise NotFoundError(missing)
            described.append(f"{label} : {item.name}")
    if body.archived_only:
        described.append("Employés archivés seulement")
    employees = EmployeeRepository(session).with_photo(
        employee_ids=body.employee_ids, department_id=body.department_id, entity_id=body.entity_id,
        archived_only=body.archived_only)
    deleted = service.purge(actor.id, employees, described, body.dry_run)
    return PurgeOut(deleted=deleted, dry_run=body.dry_run, filters=described)
