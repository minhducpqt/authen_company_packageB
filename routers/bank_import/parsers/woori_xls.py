from __future__ import annotations
import io
import pandas as pd
import hashlib
from datetime import datetime

from ..base_parser import ParseResult
from ..utils.header_synonyms import normalize_headers
from ..utils.date_utils import parse_date
from ..utils.money_utils import parse_amount

class WooriXlsParser:
    """
    Parser Woori: chấp nhận .xls, .xlsx, .csv
    Chuẩn hoá cột về:
      - txn_time (ISO)
      - description (str)
      - amount (credit - debit)
      - balance_after (float)
      - ref_no (str)
      - statement_uid (unique)
      - bank_code = "WOORI"
    """
    BANK_CODE = "WOORI"

    def can_parse(self, file_bytes: bytes, filename: str) -> bool:
        name = (filename or "").lower()
        # Ưu tiên “woori” trong tên file, nếu không vẫn cho thử đọc
        if "woori" in name:
            return True
        return name.endswith(".xls") or name.endswith(".xlsx") or name.endswith(".csv")

    def _read_any(self, file_bytes: bytes, filename: str) -> pd.DataFrame:
        name = (filename or "").lower()
        if name.endswith(".csv"):
            return pd.read_csv(io.BytesIO(file_bytes))
        # excel
        try:
            return pd.read_excel(io.BytesIO(file_bytes))
        except Exception:
            # 1 số file .xls thực chất là HTML table
            tables = pd.read_html(io.BytesIO(file_bytes))
            if not tables:
                raise
            return tables[0]

    def parse(self, file_bytes: bytes) -> ParseResult:
        try:
            df = self._read_any(file_bytes, "woori_file")
        except Exception as e:
            return {"ok": False, "errors": [f"Lỗi đọc file: {e}"], "rows": [], "row_errors": []}

        # làm sạch header
        df.columns = [str(c).strip() for c in df.columns]
        df = normalize_headers(df)

        rows, row_errors = [], []

        for idx, row in df.iterrows():
            try:
                txn_time = parse_date(row.get("txn_time"))
                desc = str(row.get("description") or "").strip()
                debit = parse_amount(row.get("debit"))
                credit = parse_amount(row.get("credit"))
                amount = credit - debit
                balance = parse_amount(row.get("balance_after"))
                ref = str(row.get("ref_no") or "").strip()

                if not txn_time:
                    raise ValueError("Thiếu ngày giao dịch")
                if amount == 0 and debit == 0 and credit == 0:
                    raise ValueError("Số tiền = 0")

                uid_src = f"{txn_time.isoformat()}|{desc}|{amount}|{balance}|{ref}"
                statement_uid = f"{self.BANK_CODE}:{hashlib.md5(uid_src.encode()).hexdigest()[:16]}"

                rows.append({
                    "bank_code": self.BANK_CODE,
                    "txn_time": txn_time.isoformat(),
                    "description": desc,
                    "amount": amount,
                    "balance_after": balance,
                    "ref_no": ref,
                    "statement_uid": statement_uid,
                    "raw": row.to_dict(),
                })
            except Exception as e:
                row_errors.append({"row": int(idx) + 1, "reason": str(e)})

        return {"ok": True, "rows": rows, "errors": [], "row_errors": row_errors}
