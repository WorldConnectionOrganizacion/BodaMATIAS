import io

import qrcode
from qrcode.constants import ERROR_CORRECT_M

from app import config


def url_invitacion(codigo: str) -> str:
    """Link unico del grupo. Es lo que codifica el QR y lo que se manda por WhatsApp.

    Invitado -> ve su invitacion. Staff logueado -> ve el control de puerta.
    """
    return f"{config.BASE_URL}/i/{codigo}"


def png_pase(codigo: str, box_size: int = 8) -> bytes:
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=box_size,
        border=2,
    )
    qr.add_data(url_invitacion(codigo))
    qr.make(fit=True)
    img = qr.make_image(fill_color="#2E2A26", back_color="#FFFFFF")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
