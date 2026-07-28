# utils/bid_ticket_qr.py
from __future__ import annotations

import base64
import io
from typing import Optional

try:
    import qrcode
    from qrcode.constants import ERROR_CORRECT_M
except ImportError:  # pragma: no cover
    qrcode = None
    ERROR_CORRECT_M = None


def qr_png_data_uri(token: str, box_size: int = 4) -> Optional[str]:
    """
    Sinh data URI PNG cho QR in trên phiếu.
    """
    text = (token or "").strip()
    if not text:
        return None
    if qrcode is None:
        return None

    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=box_size,
        border=1,
    )
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"
