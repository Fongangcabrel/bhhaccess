"""Employee photos: upload / remove (back-office) and reading through a signed, short-lived URL."""
from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile

from app.controllers.deps import get_photo_service, get_photo_signer, get_session, require
from app.core.exceptions import DomainError, NotFoundError
from app.domain.permissions import Permission
from app.models import Employee, User
from app.schemas.dto import EmployeeOut
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
