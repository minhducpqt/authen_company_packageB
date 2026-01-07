from __future__ import annotations
import io
import re
import math
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from ..base_parser import ParseResult
from ..utils.date_utils import parse_date as parse_date_util
from ..utils.money_utils import parse_amount as parse_amount_util
from ..utils.refer_code import gen_refer_code  # <- giữ nguyên

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


class WooriXlsParser:
    """
    Parser Woori: chấp nhận .xls, .xlsx, .csv.

    Chuẩn hoá về:
      - txn_time (ISO, timezone VN)
      - description (str)
      - amount (credit - debit)
      - balance_after (float)
      - ref_no (str) (Woori KHÔNG có ref rõ ràng -> để trống)
      - bank_code = "WOORI"
      - refer_code (hash rút gọn từ full dòng)

    LƯU Ý: KHÔNG tạo statement_uid ở parser. Service A sẽ tính UID theo rule mới.
    """
    BANK_CODE = "WOORI"

    WOORI_HEADER_KEYS = {
        # English (đang có)
        "transaction time and date": "txn_time",
        "currency": "currency",
        "amount withdrawn": "debit",
        "amount deposited": "credit",
        "account balance": "balance_after",
        "status": "status",
        "remarks": "remarks",
        "summary": "summary",

        # Korean (thêm mới)
        "거래일시": "txn_time",
        "통화": "currency",
        "찾으신금액": "debit",
        "맡기신금액": "credit",
        "거래후잔액": "balance_after",
        "상태": "status",
        "비고": "remarks",
        "적요": "summary",
    }

    # ---------- helpers ----------
    def can_parse(self, file_bytes: bytes, filename: str) -> bool:
        name = (filename or "").lower()
        if "woori" in name:
            return True
        return name.endswith(".xls") or name.endswith(".xlsx") or name.endswith(".csv")

    def _read_any(self, file_bytes: bytes, filename: str) -> pd.DataFrame:
        name = (filename or "").lower()
        if name.endswith(".csv"):
            return pd.read_csv(io.BytesIO(file_bytes), header=None, dtype=str)
        # Excel: đọc không đặt header (để tự dò)
        try:
            return pd.read_excel(io.BytesIO(file_bytes), header=None, dtype=str)
        except Exception:
            # một số .xls là HTML table
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
        s = s.replace('"', "").replace("’", "'").strip()
        s = re.sub(r"\s+", " ", s)
        return s

    def _detect_header_row(self, df: pd.DataFrame) -> int:
        """Tìm dòng chứa header thật của Woori (EN/KR)."""
        for i in range(min(50, len(df))):
            row_vals = [self._norm_text(v).lower() for v in df.iloc[i].tolist()]
            row_join = " | ".join(row_vals)

            # EN
            if "transaction time and date" in row_join:
                return i

            # KR
            # (chỉ cần "거래일시" là đủ đúng với file bạn đưa)
            if "거래일시" in row_join:
                return i

        return 0

    def _build_named_df(self, df_raw: pd.DataFrame, header_row: int) -> pd.DataFrame:
        raw_headers = [self._norm_text(c) for c in df_raw.iloc[header_row].tolist()]
        mapped = []
        for h in raw_headers:
            key = h.lower()
            std = self.WOORI_HEADER_KEYS.get(key)
            mapped.append(std if std else h)  # giữ nguyên nếu không map được

        df = df_raw.iloc[header_row + 1:].reset_index(drop=True)

        if df.shape[1] != len(mapped):
            mapped = (mapped + [None] * df.shape[1])[: df.shape[1]]
        df.columns = mapped

        keep_cols = [c for c in df.columns if c]
        df = df[keep_cols]
        return df

    def _parse_txn_time(self, val) -> datetime | None:
        """
        Dùng date_utils.parse_date trước, nếu fail thì thử các format Woori.
        Ví dụ: 13.10.2025 16:31:40
        """
        s = self._norm_text(val)
        if not s:
            return None

        dt = parse_date_util(s)
        if dt:
            return dt

        fmts = ["%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%d.%m.%Y"]
        for f in fmts:
            try:
                return datetime.strptime(s, f)
            except Exception:
                pass
        return None

    def _parse_amount_any(self, v) -> float | None:
        """
        Ưu tiên dùng parse_amount_util của dự án.
        Nếu kết quả None/NaN thì tự fallback cho các biến thể:
        - "1,234.56" / "1.234,56" / "1 234,56" / "+1,234" / "- 1.234"
        """
        # 1) util hiện có
        val = parse_amount_util(v)
        if val is not None and not (isinstance(val, float) and math.isnan(val)):
            return float(val)

        s = self._norm_text(v)
        if not s or s.lower() == "nan":
            return None

        # bỏ khoảng trắng & ký tự không số, giữ dấu âm
        s2 = s.replace("\u00a0", " ").replace(" ", "")
        s2 = s2.replace("VND", "").replace("vnd", "")

        # Nếu có cả '.' và ',' và ',' nằm phía sau '.' -> thường là định dạng EU ("1.234,56")
        if "." in s2 and "," in s2 and s2.rfind(",") > s2.rfind("."):
            s2 = s2.replace(".", "").replace(",", ".")
        else:
            # ngược lại coi ',' là thousand separator
            s2 = s2.replace(",", "")

        # loại các kí tự thừa
        s2 = re.sub(r"[^\d\.\-]", "", s2)
        try:
            return float(s2)
        except Exception:
            return None

    # ---------- main ----------
    def parse(self, file_bytes: bytes) -> ParseResult:
        try:
            df_raw = self._read_any(file_bytes, "woori_file")
        except Exception as e:
            return {"ok": False, "errors": [f"Lỗi đọc file: {e}"], "rows": [], "row_errors": []}

        header_row = self._detect_header_row(df_raw)
        df = self._build_named_df(df_raw, header_row)

        rows, row_errors = [], []

        for idx, row in df.iterrows():
            try:
                txn_time_dt = self._parse_txn_time(row.get("txn_time"))
                if not txn_time_dt:
                    raise ValueError("Thiếu ngày giao dịch")

                # Gán timezone VN nếu thiếu
                if txn_time_dt.tzinfo is None:
                    txn_time_dt = txn_time_dt.replace(tzinfo=VN_TZ)
                # đảm bảo biểu diễn theo VN (bỏ micro giây)
                txn_time_dt = txn_time_dt.astimezone(VN_TZ).replace(microsecond=0)
                txn_time_iso = txn_time_dt.isoformat()

                # Description: ghép remarks/summary nếu có
                remarks = self._norm_text(row.get("remarks"))
                summary = self._norm_text(row.get("summary"))
                parts = [p for p in [remarks, summary] if p]
                desc = " — ".join(parts) if parts else ""

                debit = self._parse_amount_any(row.get("debit")) or 0.0
                credit = self._parse_amount_any(row.get("credit")) or 0.0
                amount = credit - debit
                if abs(amount) < 1e-9:
                    raise ValueError("Số tiền = 0 hoặc không đọc được")

                balance = self._parse_amount_any(row.get("balance_after"))
                ref = ""  # Woori không có ref rõ ràng

                row_obj = {
                    "bank_code": self.BANK_CODE,       # chỉ để preview; khi apply sẽ override bằng TK công ty
                    "txn_time": txn_time_iso,
                    "description": desc or None,
                    "amount": amount,
                    "balance_after": balance,
                    "ref_no": ref or None,
                    # KHÔNG gửi statement_uid từ parser
                    "raw": {k: (None if (isinstance(v, float) and math.isnan(v)) else v)
                            for k, v in row.to_dict().items()},
                }

                # refer_code sinh từ full row (để đối soát sau này)
                row_obj["refer_code"] = gen_refer_code(row_obj)

                rows.append(row_obj)

            except Exception as e:
                row_errors.append({"row": int(idx) + 1, "reason": str(e)})

        errors = []
        if not rows:
            errors.append("Không tìm thấy dòng giao dịch hợp lệ nào (có thể header chưa nhận đúng).")

        return {"ok": True, "rows": rows, "errors": errors, "row_errors": row_errors}
