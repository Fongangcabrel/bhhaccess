"""Renders the printable badge QR: error-correction H with the BHH logo on a white plate.

The logo hides part of the modules; level H (30% recovery) absorbs it. Keep the logo
under ~9% of the QR area and away from the three finder squares.
"""
from io import BytesIO
from pathlib import Path

import qrcode
from PIL import Image, ImageDraw, ImageFont
from qrcode.constants import ERROR_CORRECT_H

LOGO_AREA_RATIO = 0.07  # share of the QR area covered by the logo plate


class QrImageRenderer:
    def __init__(self, logo_path: str | None) -> None:
        self._logo = Image.open(logo_path).convert("RGBA") if logo_path and Path(logo_path).exists() else None

    def render(self, token: str, label: str) -> bytes:
        """QR with the logo and the matricule underneath (PNG to download)."""
        return self._with_label(self._qr(token), label)

    def render_qr(self, token: str, border: int = 4) -> bytes:
        """QR with the logo only (the printable badge lays out the matricule itself)."""
        buffer = BytesIO()
        self._qr(token, border).convert("RGB").save(buffer, format="PNG")
        return buffer.getvalue()

    def _qr(self, token: str, border: int = 4) -> Image.Image:
        qr = qrcode.QRCode(error_correction=ERROR_CORRECT_H, box_size=10, border=border)
        qr.add_data(token)
        qr.make(fit=True)
        image = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
        if self._logo is not None:
            self._paste_logo(image)
        return image

    def _paste_logo(self, qr_image: Image.Image) -> None:
        side = qr_image.width
        target_area = side * side * LOGO_AREA_RATIO
        ratio = self._logo.width / self._logo.height
        height = int((target_area / ratio) ** 0.5)
        width = int(height * ratio)
        logo = self._logo.resize((width, height), Image.LANCZOS)
        pad = max(6, side // 60)
        plate = Image.new("RGBA", (width + 2 * pad, height + 2 * pad), "white")
        plate.paste(logo, (pad, pad), logo)
        qr_image.paste(plate, ((side - plate.width) // 2, (side - plate.height) // 2))

    @staticmethod
    def _with_label(image: Image.Image, label: str) -> bytes:
        canvas = Image.new("RGB", (image.width, image.height + 60), "white")
        canvas.paste(image.convert("RGB"), (0, 0))
        draw = ImageDraw.Draw(canvas)
        try:
            font = ImageFont.load_default(size=36)
        except TypeError:  # very old Pillow
            font = ImageFont.load_default()
        box = draw.textbbox((0, 0), label, font=font)
        draw.text(((canvas.width - (box[2] - box[0])) / 2, image.height - 8), label, fill="black", font=font)
        buffer = BytesIO()
        canvas.save(buffer, format="PNG")
        return buffer.getvalue()
