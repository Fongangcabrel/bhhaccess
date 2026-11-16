"""Excel import of employees, in two steps (SRS FR-26, FR-27).

1. ``analyse``: reads and checks every row, writes nothing. The screen shows what would be created
   and why the other rows are refused; the refused rows can be downloaded (``rejected_workbook``),
   with their original columns plus « Erreurs », to be fixed and imported again.
2. ``import_xlsx``: same checks, then creates the conforming rows (and, if asked, the missing
   entities / departments). The file name is written in the audit.

``template`` gives an empty workbook with the expected columns, an example and a short guide.
"""
import unicodedata
from dataclasses import dataclass, field
from io import BytesIO

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

from app.core.exceptions import DomainError
from app.models import Department, Employee, Entity
from app.repositories.repositories import DepartmentRepository, EmployeeRepository, EntityRepository
from app.services.audit_service import AuditService

MAX_ROWS = 5000

# Canonical field -> accepted header spellings (after normalisation), French and English.
_COLUMNS = {
    "matricule": {"matricule", "matricule interne", "employee number", "employee id"},
    "last_name": {"nom", "last name", "surname"},
    "first_name": {"prenom", "prenoms", "first name"},
    "entity": {"entite", "entity"},
    "department": {"departement", "department"},
    "job_title": {"fonction", "poste", "job title"},
}
_REQUIRED = ("matricule", "last_name", "first_name")
_LABEL = {"matricule": "matricule", "last_name": "nom", "first_name": "prénom", "entity": "entité",
          "department": "département", "job_title": "fonction"}
_MAX_LENGTH = {"matricule": 40, "last_name": 120, "first_name": 120, "job_title": 120, "entity": 120,
               "department": 120}
_TOO_LONG = {"matricule": "matricule trop long", "last_name": "nom trop long", "first_name": "prénom trop long",
             "job_title": "fonction trop longue", "entity": "nom d'entité trop long",
             "department": "nom de département trop long"}
TEMPLATE_HEADERS = ["Matricule", "Nom", "Prénom", "Entité", "Département", "Fonction"]


def _norm(text: object) -> str:
    raw = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    return " ".join(raw.strip().lower().split())


@dataclass
class CheckedRow:
    row: int
    data: dict
    errors: list[str]
    cells: tuple  # the original line, for the rejected-rows file


@dataclass
class Analysis:
    headers: list[str]
    rows: list[CheckedRow] = field(default_factory=list)
    new_entities: list[str] = field(default_factory=list)
    new_departments: list[str] = field(default_factory=list)

    @property
    def valid(self) -> list[CheckedRow]:
        return [r for r in self.rows if not r.errors]

    @property
    def rejected(self) -> list[CheckedRow]:
        return [r for r in self.rows if r.errors]


@dataclass
class RejectedRow:
    row: int
    matricule: str | None
    errors: list[str]


@dataclass
class ImportResult:
    created: int = 0
    rejected: list[RejectedRow] = field(default_factory=list)
    created_entities: list[str] = field(default_factory=list)
    created_departments: list[str] = field(default_factory=list)


class EmployeeImportService:
    def __init__(self, employees: EmployeeRepository, entities: EntityRepository,
                 departments: DepartmentRepository, audit: AuditService) -> None:
        self._employees = employees
        self._entities = entities
        self._departments = departments
        self._audit = audit

    # --- step 1: check, write nothing -----------------------------------------------
    def analyse(self, content: bytes, create_missing_org: bool) -> Analysis:
        headers, lines = self._read(content)
        analysis = Analysis(headers=headers)
        seen: set[str] = set()
        for number, data, cells in lines:
            errors = self._validate(data, seen, create_missing_org, analysis)
            if not errors:
                seen.add(data["matricule"])
            analysis.rows.append(CheckedRow(number, data, errors, cells))
        return analysis

    # --- step 2: create the conforming rows -------------------------------------------
    def import_xlsx(self, actor_id: int, content: bytes, create_missing_org: bool,
                    file_name: str | None = None) -> ImportResult:
        analysis = self.analyse(content, create_missing_org)
        result = ImportResult(
            rejected=[RejectedRow(r.row, r.data.get("matricule"), r.errors) for r in analysis.rejected])
        for checked in analysis.valid:
            data = checked.data
            entity_id, department_id = self._resolve_org(data, result)
            self._employees.add(Employee(
                matricule=data["matricule"], last_name=data["last_name"], first_name=data["first_name"],
                job_title=data.get("job_title"), entity_id=entity_id, department_id=department_id,
                extra=data["extra"],
            ))
            result.created += 1
        self._audit.record(actor_id, "employee.import", file_name, created=result.created,
                           rejected=len(result.rejected), file=file_name,
                           created_entities=result.created_entities or None,
                           created_departments=result.created_departments or None)
        return result

    # --- files ------------------------------------------------------------------------
    @staticmethod
    def rejected_workbook(analysis: Analysis, error_header: str = "Erreurs") -> bytes:
        """The refused rows with their original columns, plus the reasons: fix, then import again."""
        wb = Workbook()
        ws = wb.active
        ws.title = "Lignes rejetées"
        ws.append([*analysis.headers, error_header])
        for checked in analysis.rejected:
            cells = list(checked.cells) + [None] * (len(analysis.headers) - len(checked.cells))
            ws.append([*cells[: len(analysis.headers)], " ; ".join(checked.errors)])
        _style_header(ws, len(analysis.headers) + 1)
        ws.column_dimensions[_letter(len(analysis.headers) + 1)].width = 60
        return _save(wb)

    @staticmethod
    def template(guide: list[str], example: list[str]) -> bytes:
        wb = Workbook()
        ws = wb.active
        ws.title = "Employés"
        ws.append(TEMPLATE_HEADERS)
        ws.append(example)
        for cell in ws[2]:
            cell.font = Font(name="Arial", italic=True, color="808080")
        _style_header(ws, len(TEMPLATE_HEADERS))
        info = wb.create_sheet("Mode d'emploi")
        for line in guide:
            info.append([line])
        info.column_dimensions["A"].width = 110
        for row in info.iter_rows():
            for cell in row:
                cell.font = Font(name="Arial", bold=row[0].row == 1)
                cell.alignment = Alignment(wrap_text=True, vertical="top")
        return _save(wb)

    # --- parsing --------------------------------------------------------------------------
    @staticmethod
    def _read(content: bytes) -> tuple[list[str], list[tuple[int, dict, tuple]]]:
        try:
            sheet = load_workbook(BytesIO(content), read_only=True, data_only=True).active
        except Exception as exc:  # openpyxl raises many unrelated types on bad files
            raise DomainError("Fichier Excel illisible (.xlsx attendu)") from exc
        lines = list(sheet.iter_rows(values_only=True))
        if not lines:
            raise DomainError("Fichier vide")
        raw_headers = lines[0]
        headers = [_norm(h) for h in raw_headers]
        mapping = {i: key for i, h in enumerate(headers) for key, names in _COLUMNS.items() if h in names}
        missing = [_LABEL[c] for c in _REQUIRED if c not in set(mapping.values())]
        if missing:
            raise DomainError(f"Colonnes obligatoires absentes : {', '.join(missing)}")
        body = [(i, line) for i, line in enumerate(lines[1:], start=2) if not all(c in (None, "") for c in line)]
        if len(body) > MAX_ROWS:
            raise DomainError(f"Trop de lignes : {MAX_ROWS} maximum")
        parsed = []
        for index, line in body:
            row: dict = {"extra": {}}
            for i, cell in enumerate(line):
                value = str(cell).strip() if cell not in (None, "") else None
                if i in mapping:
                    row[mapping[i]] = value
                elif value is not None and i < len(raw_headers) and raw_headers[i]:
                    row["extra"][str(raw_headers[i]).strip()] = value
            parsed.append((index, row, tuple(line)))
        return [str(h).strip() if h is not None else "" for h in raw_headers], parsed

    # --- validation ---------------------------------------------------------------------
    def _validate(self, data: dict, seen: set[str], create_missing_org: bool, analysis: Analysis) -> list[str]:
        errors = [f"{_LABEL[name]} manquant" for name in _REQUIRED if not data.get(name)]
        errors += [f"{_TOO_LONG[name]} : {limit} caractères maximum"
                   for name, limit in _MAX_LENGTH.items() if data.get(name) and len(data[name]) > limit]
        matricule = data.get("matricule")
        if matricule and matricule in seen:
            errors.append("matricule en double dans le fichier")
        elif matricule and self._employees.by_matricule(matricule):
            errors.append("matricule déjà utilisé")
        entity_name, department_name = data.get("entity"), data.get("department")
        new_entity = bool(entity_name) and self._entities.by_name(entity_name) is None
        new_department = bool(department_name) and self._departments.by_name(department_name) is None
        if new_entity and not create_missing_org:
            errors.append(f"entité inconnue : {entity_name}")
        if new_department and not create_missing_org:
            errors.append(f"département inconnu : {department_name}")
        if not errors:  # only what a conforming row would really create
            if new_entity and entity_name not in analysis.new_entities:
                analysis.new_entities.append(entity_name)
            if new_department and department_name not in analysis.new_departments:
                analysis.new_departments.append(department_name)
        return errors

    def _resolve_org(self, data: dict, result: ImportResult) -> tuple[int | None, int | None]:
        """Entity and department are two separate lists: each is found (or created) on its own."""
        entity_name, department_name = data.get("entity"), data.get("department")
        entity = department = None
        if entity_name:
            entity = self._entities.by_name(entity_name)
            if entity is None:
                entity = self._entities.add(Entity(name=entity_name))
                result.created_entities.append(entity_name)
        if department_name:
            department = self._departments.by_name(department_name)
            if department is None:
                department = self._departments.add(Department(name=department_name))
                result.created_departments.append(department_name)
        return (entity.id if entity else None), (department.id if department else None)


def _letter(column: int) -> str:
    from openpyxl.utils import get_column_letter

    return get_column_letter(column)


def _style_header(ws, columns: int) -> None:
    fill = PatternFill("solid", fgColor="6E2139")
    for column in range(1, columns + 1):
        cell = ws.cell(1, column)
        cell.font = Font(name="Arial", bold=True, color="FFFFFF")
        cell.fill = fill
        ws.column_dimensions[_letter(column)].width = max(14, len(str(cell.value or "")) + 4)
    ws.freeze_panes = "A2"


def _save(wb: Workbook) -> bytes:
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
