"""Exports (tâches 18 à 21): Excel workbook, printable A4 landscape PDF and the badge to print.

One table definition (``ExportTable``) is rendered either way, so the Excel file and the PDF
always show the same columns as the screen. Exports leave personal data out of the system:
each one is written in the audit (who, what, filters, number of rows) by the caller.
"""
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle

from app.domain.enums import Direction, Flag, Verdict

BORDEAUX = colors.HexColor("#6E2139")
INK = colors.HexColor("#2B3A42")
PAPER = colors.HexColor("#F6F3F1")
_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")

VERDICT_LABEL = {
    Verdict.AUTHORIZED: "Autorisé", Verdict.EXIT_RECORDED: "Sortie enregistrée",
    Verdict.DENIED_ZONE: "Refusé : zone non autorisée", Verdict.DENIED_REVOKED: "Refusé : badge révoqué",
    Verdict.DENIED_EXPIRED: "Refusé : badge expiré", Verdict.DENIED_EMPLOYEE_INACTIVE: "Refusé : employé suspendu",
    Verdict.DENIED_INVALID: "QR non reconnu", Verdict.DENIED_ANTIPASSBACK: "Refusé : déjà à l'intérieur",
}
FLAG_LABEL = {
    Flag.EXIT_BADGE_REVOKED.value: "Sortie avec badge révoqué",
    Flag.EXIT_BADGE_EXPIRED.value: "Sortie avec badge expiré",
    Flag.EXIT_EMPLOYEE_SUSPENDED.value: "Sortie d'un employé suspendu", Flag.DOUBLE_ENTRY.value: "Double entrée",
    Flag.EXIT_WITHOUT_ENTRY.value: "Sortie sans entrée", Flag.UNBLOCKED.value: "Après déblocage manuel",
}
DIRECTION_LABEL = {Direction.ENTRY: "Entrée", Direction.EXIT: "Sortie"}


@dataclass(frozen=True)
class Column:
    title: str
    value: Callable[[object], object]  # str, int or datetime (shown in local time)
    width_mm: float = 30  # PDF width; Excel width is derived from it


@dataclass
class ExportTable:
    title: str
    columns: list[Column]
    rows: list
    filters: list[str]  # human-readable, e.g. "Zone : Atelier"
    author: str
    generated_at: datetime


def safe_text(value: object) -> object:
    """CSV/Excel formula injection: a cell starting with = + - @ must never be evaluated."""
    if isinstance(value, str) and value.startswith(_FORMULA_START):
        return "'" + value
    return value


class Exporter:
    def __init__(self, timezone: str) -> None:
        self._tz = ZoneInfo(timezone)

    def local(self, value: datetime) -> datetime:
        return value.astimezone(self._tz)

    # --- Excel -------------------------------------------------------------------
    def xlsx(self, table: ExportTable) -> bytes:
        """Streamed workbook (write-only: 100 000 rows without filling the memory)."""
        workbook = Workbook(write_only=True)
        sheet = workbook.create_sheet(table.title[:31])
        first_data_row = 5  # 3 lines of context, then the header row
        sheet.freeze_panes = f"A{first_data_row}"  # write-only mode: must be set before any row
        for index, column in enumerate(table.columns, start=1):
            width = max(10, column.width_mm * 0.55)
            if column.title == "Date et heure":
                width = max(width, 24)  # fit dd/mm/yyyy hh:mm:ss in Excel
            sheet.column_dimensions[get_column_letter(index)].width = width
        header_font, header_fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="6E2139")
        info = WriteOnlyCell(sheet, value=table.title)
        info.font = Font(bold=True, size=13)
        sheet.append([info])
        sheet.append([self._byline(table)])
        sheet.append(["Filtres : " + ("; ".join(table.filters) if table.filters else "aucun")])
        header = []
        for column in table.columns:
            cell = WriteOnlyCell(sheet, value=column.title)
            cell.font, cell.fill = header_font, header_fill
            cell.alignment = Alignment(vertical="center", wrap_text=True)
            header.append(cell)
        sheet.append(header)
        for row in table.rows:
            cells = []
            for column in table.columns:
                value = column.value(row)
                if isinstance(value, datetime):
                    cell = WriteOnlyCell(sheet, value=self.local(value).replace(tzinfo=None))
                    cell.number_format = "dd/mm/yyyy hh:mm:ss"
                else:
                    cell = WriteOnlyCell(sheet, value=safe_text(value) if value is not None else "")
                    if isinstance(value, str):
                        cell.data_type = "s"  # literal text, never a formula
                cells.append(cell)
            sheet.append(cells)
        last = get_column_letter(len(table.columns))
        sheet.auto_filter.ref = f"A{first_data_row - 1}:{last}{first_data_row - 1 + len(table.rows)}"
        out = BytesIO()
        workbook.save(out)
        return out.getvalue()

    # --- PDF ---------------------------------------------------------------------
    def pdf(self, table: ExportTable) -> bytes:
        """A4 landscape: title, filters, author, date and "Page x / y" on every page."""
        out = BytesIO()
        doc = SimpleDocTemplate(out, pagesize=landscape(A4), leftMargin=12 * mm, rightMargin=12 * mm,
                                topMargin=26 * mm, bottomMargin=14 * mm, title=table.title, author=table.author)
        cell = ParagraphStyle("cell", fontName="Helvetica", fontSize=7.5, leading=9, textColor=INK)
        head = ParagraphStyle("head", parent=cell, fontName="Helvetica-Bold", textColor=colors.white)
        data = [[Paragraph(escape(c.title), head) for c in table.columns]]
        for row in table.rows:
            data.append([Paragraph(escape(self._text(c.value(row))), cell) for c in table.columns])
        total_width = doc.width
        widths = [c.width_mm * mm for c in table.columns]
        scale = total_width / sum(widths)
        grid = LongTable(data, colWidths=[w * scale for w in widths], repeatRows=1)
        grid.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BORDEAUX),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PAPER]),
            ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#E2DAD6")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story = [grid] if table.rows else [Spacer(1, 4 * mm), Paragraph("Aucune ligne pour ces filtres.", cell)]
        byline, filters = self._byline(table), "Filtres : " + ("; ".join(table.filters) if table.filters else "aucun")

        def decorate(page: pdf_canvas.Canvas, _doc) -> None:
            width, height = landscape(A4)
            page.saveState()
            page.setFillColor(BORDEAUX)
            page.setFont("Helvetica-Bold", 13)
            page.drawString(12 * mm, height - 12 * mm, table.title)
            page.setFillColor(INK)
            page.setFont("Helvetica", 8)
            page.drawString(12 * mm, height - 17 * mm, byline)
            page.drawString(12 * mm, height - 21 * mm, filters[:180])
            page.setStrokeColor(BORDEAUX)
            page.line(12 * mm, height - 23 * mm, width - 12 * mm, height - 23 * mm)
            page.restoreState()

        doc.build(story, onFirstPage=decorate, onLaterPages=decorate, canvasmaker=_NumberedCanvas)
        return out.getvalue()

    def _text(self, value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, datetime):
            return self.local(value).strftime("%d/%m/%Y %H:%M:%S")
        return str(value)

    def _byline(self, table: ExportTable) -> str:
        when = self.local(table.generated_at).strftime("%d/%m/%Y à %H:%M")
        return f"Exporté par {table.author} le {when} · {len(table.rows)} ligne(s) · BHH Access"


class _NumberedCanvas(pdf_canvas.Canvas):
    """Two-pass canvas so each page can say "Page x / y"."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pages: list[dict] = []

    def showPage(self):  # noqa: N802 (reportlab API)
        self._pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._pages)
        for state in self._pages:
            self.__dict__.update(state)
            width, _ = self._pagesize
            self.setFont("Helvetica", 7.5)
            self.setFillColor(INK)
            self.drawRightString(width - 12 * mm, 8 * mm, f"Page {self._pageNumber} / {total}")
            super().showPage()
        super().save()


# --- the badge to print ----------------------------------------------------------
CARD_W, CARD_H = 54 * mm, 85.6 * mm  # ID-1 card, portrait (worn at the neck)
QR_BORDER = 1  # modules; the white card margin around the image completes the quiet zone
QR_SIDE = 46 * mm  # image incl. a 1-module border: the code itself is ~44 mm (>= 4 cm, TRD §4)


def badge_pdf(qr_png: bytes, matricule: str, logo_path: str | None) -> bytes:
    """One badge at real size on an A4 page, with cut marks: only the QR (logo inside) and the matricule."""
    out = BytesIO()
    page = pdf_canvas.Canvas(out, pagesize=A4)
    page.setTitle(f"Badge {matricule}")
    width, height = A4
    x, y = (width - CARD_W) / 2, (height - CARD_H) / 2
    # cut marks
    page.setStrokeColor(colors.HexColor("#9A8F8B"))
    page.setDash(2, 2)
    page.setLineWidth(0.4)
    page.roundRect(x, y, CARD_W, CARD_H, 3 * mm, stroke=1, fill=0)
    page.setDash()
    # header band
    band = 13 * mm
    page.setFillColor(BORDEAUX)
    page.roundRect(x, y + CARD_H - band, CARD_W, band, 3 * mm, stroke=0, fill=1)
    page.rect(x, y + CARD_H - band, CARD_W, band / 2, stroke=0, fill=1)
    if logo_path:
        try:
            page.drawImage(ImageReader(logo_path), x + 3 * mm, y + CARD_H - band + 2 * mm, 9 * mm, 9 * mm,
                           mask="auto", preserveAspectRatio=True)
        except OSError:
            pass
    page.setFillColor(colors.white)
    page.setFont("Helvetica-Bold", 11)
    page.drawString(x + 14 * mm, y + CARD_H - band + 4.6 * mm, "BHH Access")
    # QR, then the matricule (used for manual entry when the QR is damaged)
    qr_y = y + CARD_H - band - 4 * mm - QR_SIDE
    page.drawImage(ImageReader(BytesIO(qr_png)), x + (CARD_W - QR_SIDE) / 2, qr_y, QR_SIDE, QR_SIDE)
    page.setFillColor(INK)
    page.setFont("Helvetica-Bold", 15)
    page.drawCentredString(x + CARD_W / 2, qr_y - 9 * mm, matricule)
    page.setFont("Helvetica", 6.5)
    page.setFillColor(colors.HexColor("#6B6360"))
    page.drawCentredString(x + CARD_W / 2, qr_y - 14 * mm, "Badge personnel - à porter de façon visible")
    # printing instructions, outside the card
    page.setFont("Helvetica", 8)
    page.drawCentredString(width / 2, y - 12 * mm, "Imprimer à 100 % (sans « ajuster à la page ») : QR de 44 mm.")
    page.drawCentredString(width / 2, y - 16 * mm,
                           "Découper sur le pointillé, plastifier, puis tester la lecture avant remise.")
    page.showPage()
    page.save()
    return out.getvalue()


def join_flags(flags: Iterable[str]) -> str:
    return ", ".join(FLAG_LABEL.get(f, f) for f in flags)
