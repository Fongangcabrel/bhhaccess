from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile, status

from app.controllers.deps import (
    get_bulk_service,
    get_employee_service,
    get_import_service,
    get_photo_signer,
    require,
)
from app.controllers.photo_controller import employee_out
from app.core.exceptions import DomainError
from app.core.i18n import request_lang, tr
from app.domain.enums import BulkAction, EmployeeStatus
from app.domain.permissions import Permission
from app.models import User
from app.schemas.dto import (
    ArchiveIn,
    BulkFailureOut,
    BulkIn,
    BulkOut,
    EmployeeIn,
    EmployeeOut,
    EmployeeStatusIn,
    EmployeeUpdateIn,
    ImportCheckOut,
    ImportPreviewRow,
    ImportReport,
    RejectedRow,
)
from app.services.bulk_service import RIGHT, BulkService
from app.services.employee_service import EmployeeService
from app.services.import_service import EmployeeImportService
from app.services.permission_service import PermissionService
from app.services.photo_service import PhotoUrlSigner

router = APIRouter(prefix="/employees", tags=["employees"])


@router.post("", response_model=EmployeeOut, status_code=status.HTTP_201_CREATED)
def create_employee(body: EmployeeIn, actor: User = Depends(require(Permission.EMPLOYEES_EDIT)),
                    service: EmployeeService = Depends(get_employee_service)):
    return service.create(actor.id, **body.model_dump())


XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PREVIEW_ROWS = 20


def _content(file: UploadFile, request: Request) -> bytes:
    """The uploaded workbook, refused beyond the size limit (read one byte more to know)."""
    limit = getattr(request.app.state, "import_max_bytes", 5 * 1024 * 1024)
    content = file.file.read(limit + 1)
    if len(content) > limit:
        raise DomainError(f"Fichier trop lourd : {limit // (1024 * 1024)} Mo maximum")
    return content


def _rejected(rows, lang: str) -> list[RejectedRow]:
    return [RejectedRow(row=r.row, matricule=r.matricule if hasattr(r, "matricule") else r.data.get("matricule"),
                        errors=[tr(e, lang) for e in r.errors]) for r in rows]


@router.get("/import/template.xlsx", response_class=Response)
def import_template(lang: str = Depends(request_lang),
                    _: User = Depends(require(Permission.EMPLOYEES_IMPORT)),
                    service: EmployeeImportService = Depends(get_import_service)):
    """Empty workbook with the expected columns, an example row and a short guide."""
    example = ["EMP-0001", "Ngono", "Paul", "BHH Industrie", "Production", "Soudeur"]
    content = service.template(TEMPLATE_GUIDE[lang], example)
    return Response(content, media_type=XLSX,
                    headers={"Content-Disposition": 'attachment; filename="modele-import-employes.xlsx"'})


@router.post("/import/check", response_model=ImportCheckOut)
def check_import(request: Request, file: UploadFile = File(...), create_missing_org: bool = False,
                 lang: str = Depends(request_lang),
                 _: User = Depends(require(Permission.EMPLOYEES_IMPORT)),
                 service: EmployeeImportService = Depends(get_import_service)):
    """Step 1: read and check every row; nothing is written."""
    analysis = service.analyse(_content(file, request), create_missing_org)
    return ImportCheckOut(
        file_name=file.filename, total=len(analysis.rows), valid=len(analysis.valid),
        rejected=_rejected(analysis.rejected, lang),
        new_entities=analysis.new_entities, new_departments=analysis.new_departments,
        preview=[ImportPreviewRow(row=r.row, **{k: r.data.get(k) for k in ImportPreviewRow.model_fields if k != "row"})
                 for r in analysis.valid[:PREVIEW_ROWS]],
    )


@router.post("/import/rejected.xlsx", response_class=Response)
def rejected_rows(request: Request, file: UploadFile = File(...), create_missing_org: bool = False,
                  lang: str = Depends(request_lang),
                  _: User = Depends(require(Permission.EMPLOYEES_IMPORT)),
                  service: EmployeeImportService = Depends(get_import_service)):
    """The refused rows, original columns + reasons: fix them in Excel, then import this file."""
    analysis = service.analyse(_content(file, request), create_missing_org)
    for row in analysis.rejected:
        row.errors = [tr(e, lang) for e in row.errors]
    content = service.rejected_workbook(analysis, "Errors" if lang == "en" else "Erreurs")
    return Response(content, media_type=XLSX,
                    headers={"Content-Disposition": 'attachment; filename="lignes-rejetees.xlsx"'})


@router.post("/import", response_model=ImportReport)
def import_employees(request: Request, file: UploadFile = File(...), create_missing_org: bool = False,
                     lang: str = Depends(request_lang),
                     actor: User = Depends(require(Permission.EMPLOYEES_IMPORT)),
                     service: EmployeeImportService = Depends(get_import_service)):
    """Step 2: create the conforming rows; return the rejected ones with the reasons."""
    result = service.import_xlsx(actor.id, _content(file, request), create_missing_org, file.filename)
    return ImportReport(
        created=result.created, created_entities=result.created_entities,
        created_departments=result.created_departments, rejected=_rejected(result.rejected, lang),
    )


TEMPLATE_GUIDE = {
    "fr": [
        "Import des employés : mode d'emploi",
        "Une ligne par employé, dans l'onglet « Employés ». Remplacez la ligne d'exemple (en gris).",
        "Colonnes obligatoires : Matricule, Nom, Prénom. Le matricule est unique : il est imprimé sur le badge.",
        "Colonnes facultatives : Entité, Département, Fonction. Entité et département doivent exister dans "
        "« Entités et départements », sauf si vous cochez « Créer les entités et départements qui n'existent pas ».",
        "Les autres colonnes (ex. Site, Téléphone) sont conservées telles quelles dans la fiche.",
        "Longueurs maximales : matricule 40 caractères ; nom, prénom, fonction, entité, département 120.",
        "Taille maximale : 5 Mo et 5 000 lignes par fichier.",
        "Dans l'application : « Vérifier le fichier » montre ce qui sera créé et les lignes refusées, sans rien "
        "enregistrer. Les lignes refusées se téléchargent en Excel avec la raison : corrigez-les puis "
        "importez ce fichier.",
    ],
    "en": [
        "Employee import: how to fill this file",
        "One row per employee, in the « Employés » sheet. Replace the example row (in grey).",
        "Required columns: Matricule (employee number), Nom (last name), Prénom (first name). The employee number "
        "is unique: it is printed on the badge.",
        "Optional columns: Entité (entity), Département (department), Fonction (job title). Entity and department "
        "must exist in « Entities and departments », unless you tick « Create the entities and departments that do "
        "not exist ».",
        "Other columns (e.g. Site, Phone) are kept as they are in the employee file.",
        "Maximum lengths: employee number 40 characters; names, job title, entity, department 120.",
        "Maximum size: 5 MB and 5,000 rows per file.",
        "In the app: « Check the file » shows what will be created and the refused rows, without saving anything. "
        "The refused rows can be downloaded as Excel with the reason: fix them, then import that file.",
    ],
}


@router.post("/bulk", response_model=BulkOut)
def bulk(body: BulkIn, lang: str = Depends(request_lang),
         actor: User = Depends(require(Permission.EMPLOYEES_VIEW)),
         service: BulkService = Depends(get_bulk_service)):
    """Same change for many employees; each one is checked and audited as if done by hand."""
    PermissionService().require(actor, RIGHT[body.action])
    employees, target = service.targets(body.employee_ids, body.in_department_id, body.in_entity_id)
    if body.dry_run:
        return BulkOut(action=body.action, dry_run=True, target=target, total=len(employees), done=0,
                       unchanged=0, failed=[])
    org = {k: getattr(body, k) for k in ("entity_id", "department_id") if k in body.model_fields_set}
    result = service.run(actor.id, body.action, employees, target,
                         org_changes=org if body.action == BulkAction.ORG else None,
                         zone_ids=body.zone_ids, reason=body.reason)
    return BulkOut(action=body.action, dry_run=False, target=target, total=result.total, done=len(result.done),
                   unchanged=len(result.unchanged),
                   failed=[BulkFailureOut(employee_id=f.employee_id, matricule=f.matricule, reason=tr(f.reason, lang))
                           for f in result.failed])


@router.get("", response_model=list[EmployeeOut])
def search_employees(q: str | None = None, status: EmployeeStatus | None = None,
                     limit: int = Query(50, le=200), offset: int = 0,
                     _: User = Depends(require(Permission.EMPLOYEES_VIEW)),
                     service: EmployeeService = Depends(get_employee_service)):
    """Without ``status``: current staff (active + suspended). ``status=ARCHIVE``: the archive."""
    return service.search(q, limit, offset, status)


@router.get("/{employee_id}", response_model=EmployeeOut)
def get_employee(employee_id: int, _: User = Depends(require(Permission.EMPLOYEES_VIEW)),
                 service: EmployeeService = Depends(get_employee_service),
                 signer: PhotoUrlSigner = Depends(get_photo_signer)):
    """The file view: carries a signed photo URL (lists only say ``has_photo``)."""
    return employee_out(service.get(employee_id), signer)


@router.patch("/{employee_id}", response_model=EmployeeOut)
def update_employee(employee_id: int, body: EmployeeUpdateIn,
                    actor: User = Depends(require(Permission.EMPLOYEES_EDIT)),
                    service: EmployeeService = Depends(get_employee_service)):
    return service.update(actor.id, employee_id, body.model_dump(exclude_unset=True))


@router.patch("/{employee_id}/status", response_model=EmployeeOut)
def change_status(employee_id: int, body: EmployeeStatusIn,
                  actor: User = Depends(require(Permission.EMPLOYEES_EDIT)),
                  service: EmployeeService = Depends(get_employee_service)):
    """Suspend / reactivate (FR-22). Archiving is a separate action."""
    return service.change_status(actor.id, employee_id, body.status)


@router.post("/{employee_id}/archive", response_model=EmployeeOut)
def archive_employee(employee_id: int, body: ArchiveIn,
                     actor: User = Depends(require(Permission.EMPLOYEES_ARCHIVE)),
                     service: EmployeeService = Depends(get_employee_service)):
    return service.archive(actor.id, employee_id, body.reason)


@router.post("/{employee_id}/restore", response_model=EmployeeOut)
def restore_employee(employee_id: int, actor: User = Depends(require(Permission.EMPLOYEES_ARCHIVE)),
                     service: EmployeeService = Depends(get_employee_service)):
    return service.restore(actor.id, employee_id)
