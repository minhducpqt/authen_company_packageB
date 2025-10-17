# routers/bank_import/parsers/woori_xls.py
from __future__ import annotations
import io
import re
import pandas as pd
import hashlib
from datetime import datetime

from ..base_parser import ParseResult
from ..utils.date_utils import parse_date as parse_date_util
from ..utils.money_utils import parse_amount

class WooriXlsParser:
    """
    Parser Woori: chấp nhận .xls, .xlsx, .csv.

    Chuẩn hoá về:
      - txn_time (ISO)
      - description (str)
      - amount (credit - debit)
      - balance_after (float)
      - ref_no (str) (Woori KHÔNG có ref rõ ràng -> để trống)
      - statement_uid (unique)
      - bank_code = "WOORI"
    """
    BANK_CODE = "WOORI"

    WOORI_HEADER_KEYS = {
        "transaction time and date": "txn_time",
        "currency": "currency",
        "amount withdrawn": "debit",
        "amount deposited": "credit",
        "account balance": "balance_after",
        "status": "status",
        "remarks": "remarks",
        "summary": "summary",
    }

    def can_parse(self, file_bytes: bytes, filename: str) -> bool:
        name = (filename or "").lower()
        if "woori" in name:
            return True
        return name.endswith(".xls") or name.endswith(".xlsx") or name.endswith(".csv")

    # ---------- helpers ----------
    def _read_any(self, file_bytes: bytes, filename: str) -> pd.DataFrame:
        name = (filename or "").lower()
        if name.endswith(".csv"):
            return pd.read_csv(io.BytesIO(file_bytes), header=None, dtype=str)
        # Excel: đọc không đặt header (để tự dò)
        try:
            return pd.read_excel(io.BytesIO(file_bytes), header=None, dtype=str)
        except Exception:
            # .xls là HTML table
            tables = pd.read_html(io.BytesIO(file_bytes))
            if not tables:
                raise
            df = tables[0]
            df = df.astype(str)
            return df

    @staticmethod
    def _norm_text(x: str) -> str:
        if x is None:
            return ""
        s = str(x)
        # bỏ ngoặc kép, khoảng trắng thừa
        s = s.replace('"', "").replace("’", "'").strip()
        # collapse whitespace
        s = re.sub(r"\s+", " ", s)
        return s

    def _detect_header_row(self, df: pd.DataFrame) -> int:
        """
        Tìm dòng chứa header thật của Woori.
        Ví dụ cell: `"                        Transaction time and date"`
        """
        for i in range(min(50, len(df))):
            row_vals = [self._norm_text(v).lower() for v in df.iloc[i].tolist()]
            row_join = " | ".join(row_vals)
            if "transaction time and date" in row_join:
                return i
        # fallback: không tìm thấy -> 0
        return 0

    def _build_named_df(self, df_raw: pd.DataFrame, header_row: int) -> pd.DataFrame:
        # Lấy hàng header
        raw_headers = [self._norm_text(c) for c in df_raw.iloc[header_row].tolist()]
        # Map header Woori -> tên chuẩn
        mapped = []
        for h in raw_headers:
            key = h.lower()
            std = self.WOORI_HEADER_KEYS.get(key)
            mapped.append(std if std else h)  # giữ nguyên nếu không map được

        # Cắt phần dữ liệu bên dưới header
        df = df_raw.iloc[header_row + 1 : ].reset_index(drop=True)
        # Gán tên cột
        # Nếu số cột dữ liệu nhiều hơn header (hiếm), cắt bớt; nếu ít hơn, pad thêm
        if df.shape[1] != len(mapped):
            mapped = (mapped + [None] * df.shape[1])[: df.shape[1]]
        df.columns = mapped

        # loại bỏ các cột không tên (None)
        keep_cols = [c for c in df.columns if c]
        df = df[keep_cols]

        return df

    def _parse_txn_time(self, val) -> datetime | None:
        """
        Dùng date_utils.parse_date trước, nếu fail thì thử các format Woori thực tế.
        Ví dụ: 13.10.2025 16:31:40
        """
        s = self._norm_text(val)
        if not s:
            return None

        # 1) util của dự án
        dt = parse_date_util(s)
        if dt:
            return dt

        # 2) fallback các format Woori
        fmts = [
            "%d.%m.%Y %H:%M:%S",
            "%d.%m.%Y %H:%M",
            "%d.%m.%Y",
        ]
        for f in fmts:
            try:
                return datetime.strptime(s, f)
            except Exception:
                pass
        return None

    # ---------- main ----------
    def parse(self, file_bytes: bytes) -> ParseResult:
        try:
            df_raw = self._read_any(file_bytes, "woori_file")
        except Exception as e:
            return {"ok": False, "errors": [f"Lỗi đọc file: {e}"], "rows": [], "row_errors": []}

        # dò header
        header_row = self._detect_header_row(df_raw)
        df = self._build_named_df(df_raw, header_row)

        rows, row_errors = [], []

        for idx, row in df.iterrows():
            try:
                txn_time = self._parse_txn_time(row.get("txn_time"))
                desc = ""
                # ghép remarks/summary nếu có
                remarks = self._norm_text(row.get("remarks"))
                summary = self._norm_text(row.get("summary"))
                parts = [p for p in [remarks, summary] if p]
                desc = " — ".join(parts) if parts else ""

                debit = parse_amount(row.get("debit"))
                credit = parse_amount(row.get("credit"))
                amount = (credit or 0) - (debit or 0)

                balance = parse_amount(row.get("balance_after"))
                ref = ""  # Woori không có ref rõ ràng

                if not txn_time:
                    raise ValueError("Thiếu ngày giao dịch")
                if (debit or 0) == 0 and (credit or 0) == 0:
                    raise ValueError("Số tiền = 0")

                uid_src = f"{txn_time.isoformat()}|{desc}|{amount}|{balance}|{ref}"
                statement_uid = f"{self.BANK_CODE}:{hashlib.md5(uid_src.encode()).hexdigest()[:16]}"

                rows.append({
                    "bank_code": self.BANK_CODE,
                    "txn_time": txn_time.isoformat(),
                    "description": desc or None,
                    "amount": amount,
                    "balance_after": balance,
                    "ref_no": ref or None,
                    "statement_uid": statement_uid,
                    "raw": {k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()},
                })
            except Exception as e:
                row_errors.append({"row": int(idx) + 1, "reason": str(e)})

        errors = []
        if not rows:
            errors.append("Không tìm thấy dòng giao dịch hợp lệ nào (có thể header chưa nhận đúng).")

        return {"ok": True, "rows": rows, "errors": errors, "row_errors": row_errors}
