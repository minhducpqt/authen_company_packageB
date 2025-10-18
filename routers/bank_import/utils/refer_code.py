# utils/refer_code.py
from __future__ import annotations
import hashlib
import json
from typing import Any, Dict


def gen_refer_code(row: Dict[str, Any]) -> str:
    """
    Sinh mã tham chiếu ngắn (refer_code) từ full nội dung dòng sao kê.

    - Ổn định theo dữ liệu đầu vào.
    - Không đụng đến statement_uid (độc lập).
    - Trả về chuỗi dạng: REF:XXXXXXXX (8 hex in hoa)
    """
    # Chỉ giữ các trường ổn định; raw có thể lớn nhưng vẫn OK cho tính duy nhất
    try:
        base_str = json.dumps(row, sort_keys=True, ensure_ascii=False)
    except Exception:
        base_str = str(row)
    h = hashlib.sha256(base_str.encode("utf-8")).hexdigest()[:8]
    return f"REF:{h.upper()}"
