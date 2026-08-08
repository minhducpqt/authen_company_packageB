# utils/project_import_verifier.py
"""
Verify dữ liệu Excel import dự án (Service B Preview).

Chỉ chạy ở Service B — không gọi API validation mới trên Service A.
"""
from __future__ import annotations

from collections import Counter
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Thresholds — khai báo tập trung, dễ config sau
# ---------------------------------------------------------------------------
MIN_AMOUNT = 1_000_000
MAX_AMOUNT = 100_000_000_000
OUTLIER_MULTIPLIER = 10

# “% tròn/hợp lý”: không còn phần thập phân sau quantize
PROJECT_DEPOSIT_PERCENT_QUANTIZE = Decimal("0.0001")
# Bucket so sánh % cọc từng lô (không so sánh float thô)
LOT_DEPOSIT_PERCENT_QUANTIZE = Decimal("0.0001")


# Error / warning codes
CODE_INVALID_STARTING_PRICE = "INVALID_STARTING_PRICE"
CODE_INVALID_DEPOSIT = "INVALID_DEPOSIT"
CODE_DEPOSIT_GREATER_THAN_STARTING_PRICE = "DEPOSIT_GREATER_THAN_STARTING_PRICE"
CODE_STARTING_PRICE_TOO_LOW = "STARTING_PRICE_TOO_LOW"
CODE_STARTING_PRICE_TOO_HIGH = "STARTING_PRICE_TOO_HIGH"
CODE_DEPOSIT_TOO_LOW = "DEPOSIT_TOO_LOW"
CODE_DEPOSIT_TOO_HIGH = "DEPOSIT_TOO_HIGH"
CODE_STARTING_PRICE_OUTLIER = "STARTING_PRICE_OUTLIER"
CODE_UNUSUAL_PROJECT_DEPOSIT_PERCENT = "UNUSUAL_PROJECT_DEPOSIT_PERCENT"
CODE_DEPOSIT_PERCENT_DIFFERS_FROM_PROJECT = "DEPOSIT_PERCENT_DIFFERS_FROM_PROJECT"


def _issue(code: str, message: str, field: Optional[str] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {"code": code, "message": message}
    if field:
        out["field"] = field
    return out


def _to_decimal(v: Any) -> Optional[Decimal]:
    if v is None or v == "" or v == "NaN":
        return None
    if isinstance(v, bool):
        return None
    try:
        if isinstance(v, Decimal):
            return v
        if isinstance(v, int):
            return Decimal(v)
        if isinstance(v, float):
            # tránh binary float nhiễu — dùng str
            return Decimal(str(v))
        s = str(v).strip().replace(",", "").replace(" ", "")
        if not s:
            return None
        return Decimal(s)
    except (InvalidOperation, ValueError, TypeError):
        return None


def is_strict_non_negative_integer(v: Any) -> bool:
    """Số nguyên ≥ 0 (Excel float 1.0 chấp nhận; 1.5 không)."""
    if v is None or v == "" or v == "NaN":
        return False
    if isinstance(v, bool):
        return False
    if isinstance(v, int):
        return v >= 0
    if isinstance(v, float):
        return v >= 0 and v.is_integer()
    d = _to_decimal(v)
    if d is None or d < 0:
        return False
    return d == d.to_integral_value()


def as_int_amount(v: Any) -> Optional[int]:
    if not is_strict_non_negative_integer(v):
        return None
    if isinstance(v, int):
        return int(v)
    if isinstance(v, float):
        return int(v)
    d = _to_decimal(v)
    if d is None:
        return None
    return int(d)


def is_round_project_percent(pct: Decimal) -> bool:
    """
    % cọc tổng dự án “tròn/hợp lý”.
    Hiện tại: phần trăm là số nguyên (20, 30, 50…), không chấp nhận 18.2222.
    Đổi rule tại đây khi product muốn 0.5% v.v.
    """
    if pct is None:
        return False
    q = pct.quantize(PROJECT_DEPOSIT_PERCENT_QUANTIZE, rounding=ROUND_HALF_UP)
    return q == q.to_integral_value()


def quantize_lot_percent(pct: Decimal) -> Decimal:
    return pct.quantize(LOT_DEPOSIT_PERCENT_QUANTIZE, rounding=ROUND_HALF_UP)


class ProjectImportVerifier:
    """
    Verify lô sau khi parse Excel.
    lots: list dict có row, project_code, lot_code, starting_price, deposit_amount
    (starting_price/deposit_amount: int | None | 'NaN' | raw invalid)
    """

    def __init__(
        self,
        lots: List[Dict[str, Any]],
        *,
        min_amount: int = MIN_AMOUNT,
        max_amount: int = MAX_AMOUNT,
        outlier_multiplier: int = OUTLIER_MULTIPLIER,
    ):
        self.lots = lots or []
        self.min_amount = min_amount
        self.max_amount = max_amount
        self.outlier_multiplier = outlier_multiplier

    # ----- Rule 1 -----
    def verify_integer_fields(
        self, lot: Dict[str, Any]
    ) -> Tuple[List[Dict[str, Any]], Optional[int], Optional[int]]:
        errors: List[Dict[str, Any]] = []
        sp_raw = lot.get("starting_price")
        dp_raw = lot.get("deposit_amount")

        sp: Optional[int] = None
        dp: Optional[int] = None

        if sp_raw is None or sp_raw == "":
            errors.append(
                _issue(
                    CODE_INVALID_STARTING_PRICE,
                    "Giá khởi điểm bắt buộc và phải là số nguyên.",
                    "starting_price",
                )
            )
        elif not is_strict_non_negative_integer(sp_raw):
            errors.append(
                _issue(
                    CODE_INVALID_STARTING_PRICE,
                    "Giá khởi điểm phải là số nguyên.",
                    "starting_price",
                )
            )
        else:
            sp = as_int_amount(sp_raw)

        if dp_raw is None or dp_raw == "":
            errors.append(
                _issue(
                    CODE_INVALID_DEPOSIT,
                    "Tiền đặt cọc bắt buộc và phải là số nguyên.",
                    "deposit_amount",
                )
            )
        elif not is_strict_non_negative_integer(dp_raw):
            errors.append(
                _issue(
                    CODE_INVALID_DEPOSIT,
                    "Tiền đặt cọc phải là số nguyên.",
                    "deposit_amount",
                )
            )
        else:
            dp = as_int_amount(dp_raw)

        return errors, sp, dp

    # ----- Rule 2 ranges -----
    def verify_value_range(
        self, *, starting_price: Optional[int], deposit: Optional[int]
    ) -> List[Dict[str, Any]]:
        warnings: List[Dict[str, Any]] = []
        if starting_price is None or deposit is None:
            return warnings

        if deposit > starting_price:
            warnings.append(
                _issue(
                    CODE_DEPOSIT_GREATER_THAN_STARTING_PRICE,
                    f"Tiền đặt cọc ({deposit:,}) lớn hơn giá khởi điểm ({starting_price:,}).",
                    "deposit_amount",
                )
            )
        if deposit < self.min_amount:
            warnings.append(
                _issue(
                    CODE_DEPOSIT_TOO_LOW,
                    f"Tiền đặt cọc ({deposit:,}) nhỏ hơn {self.min_amount:,} VNĐ.",
                    "deposit_amount",
                )
            )
        if starting_price < self.min_amount:
            warnings.append(
                _issue(
                    CODE_STARTING_PRICE_TOO_LOW,
                    f"Giá khởi điểm ({starting_price:,}) nhỏ hơn {self.min_amount:,} VNĐ.",
                    "starting_price",
                )
            )
        if deposit > self.max_amount:
            warnings.append(
                _issue(
                    CODE_DEPOSIT_TOO_HIGH,
                    f"Tiền đặt cọc ({deposit:,}) lớn hơn {self.max_amount:,} VNĐ.",
                    "deposit_amount",
                )
            )
        if starting_price > self.max_amount:
            warnings.append(
                _issue(
                    CODE_STARTING_PRICE_TOO_HIGH,
                    f"Giá khởi điểm ({starting_price:,}) lớn hơn {self.max_amount:,} VNĐ.",
                    "starting_price",
                )
            )
        return warnings

    def calculate_average_starting_price(
        self, valid_starting_prices: List[int]
    ) -> Optional[Decimal]:
        if not valid_starting_prices:
            return None
        total = sum(Decimal(x) for x in valid_starting_prices)
        return total / Decimal(len(valid_starting_prices))

    def verify_starting_price_outlier(
        self, starting_price: int, average: Optional[Decimal]
    ) -> List[Dict[str, Any]]:
        if average is None or average <= 0:
            return []
        warnings: List[Dict[str, Any]] = []
        sp = Decimal(starting_price)
        mult = Decimal(self.outlier_multiplier)
        hi = average * mult
        lo = average / mult
        if sp > hi:
            warnings.append(
                _issue(
                    CODE_STARTING_PRICE_OUTLIER,
                    f"Giá khởi điểm ({starting_price:,}) cao bất thường "
                    f"(> {self.outlier_multiplier}× trung bình {average:,.0f}).",
                    "starting_price",
                )
            )
        if sp < lo:
            warnings.append(
                _issue(
                    CODE_STARTING_PRICE_OUTLIER,
                    f"Giá khởi điểm ({starting_price:,}) thấp bất thường "
                    f"(< 1/{self.outlier_multiplier} trung bình {average:,.0f}).",
                    "starting_price",
                )
            )
        return warnings

    def calculate_project_deposit_percent(
        self, total_deposit: int, total_starting: int
    ) -> Optional[Decimal]:
        if total_starting <= 0:
            return None
        return (Decimal(total_deposit) * Decimal(100)) / Decimal(total_starting)

    def verify_project_deposit_percent(
        self, pct: Optional[Decimal]
    ) -> List[Dict[str, Any]]:
        if pct is None:
            return []
        if is_round_project_percent(pct):
            return []
        return [
            _issue(
                CODE_UNUSUAL_PROJECT_DEPOSIT_PERCENT,
                f"Tỷ lệ cọc tổng dự án {pct.quantize(Decimal('0.0001'))}% không phải % tròn (vd 20, 30, 50).",
            )
        ]

    def determine_representative_deposit_percent(
        self, lot_percents: List[Decimal]
    ) -> Optional[Decimal]:
        if not lot_percents:
            return None
        keys = [quantize_lot_percent(p) for p in lot_percents]
        counts = Counter(keys)
        # majority; tie-break: higher count then lower percent
        best = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        return best

    def verify_lot_deposit_percent(
        self,
        lot_pct: Decimal,
        representative: Optional[Decimal],
    ) -> List[Dict[str, Any]]:
        if representative is None:
            return []
        q = quantize_lot_percent(lot_pct)
        rep = quantize_lot_percent(representative)
        if q == rep:
            return []
        return [
            _issue(
                CODE_DEPOSIT_PERCENT_DIFFERS_FROM_PROJECT,
                f"Tỷ lệ tiền cọc của lô là {q}%, khác với tỷ lệ cọc phổ biến của dự án là {rep}%.",
                "deposit_amount",
            )
        ]

    def run(self) -> Dict[str, Any]:
        """
        Returns verification payload for preview.
        """
        # Pass 1: integers + valid pairs
        working: List[Dict[str, Any]] = []
        for lot in self.lots:
            row = dict(lot)
            row_no = int(row.get("row") or row.get("row_number") or 0)
            errs, sp, dp = self.verify_integer_fields(row)
            warns = self.verify_value_range(starting_price=sp, deposit=dp)
            row["_sp"] = sp
            row["_dp"] = dp
            row["_errors"] = list(errs)
            row["_warnings"] = list(warns)
            row["row"] = row_no or row.get("row")
            working.append(row)

        # Group by project for project-level metrics
        by_project: Dict[str, List[Dict[str, Any]]] = {}
        for row in working:
            pc = row.get("project_code") or ""
            by_project.setdefault(pc, []).append(row)

        project_summaries: List[Dict[str, Any]] = []
        lot_results: List[Dict[str, Any]] = []
        total_error_count = 0
        total_warning_count = 0
        grand_sp = 0
        grand_dp = 0
        grand_valid = 0

        for project_code, rows in by_project.items():
            valid_pairs: List[Tuple[Dict[str, Any], int, int]] = []
            for row in rows:
                sp, dp = row["_sp"], row["_dp"]
                if sp is not None and dp is not None and not row["_errors"]:
                    valid_pairs.append((row, sp, dp))

            valid_sps = [sp for _, sp, _ in valid_pairs]
            avg = self.calculate_average_starting_price(valid_sps)
            total_sp = sum(sp for _, sp, _ in valid_pairs)
            total_dp = sum(dp for _, _, dp in valid_pairs)
            project_pct = self.calculate_project_deposit_percent(total_dp, total_sp)
            project_warnings = self.verify_project_deposit_percent(project_pct)

            lot_pcts: List[Decimal] = []
            for _, sp, dp in valid_pairs:
                if sp > 0:
                    lot_pcts.append((Decimal(dp) * Decimal(100)) / Decimal(sp))

            representative = self.determine_representative_deposit_percent(lot_pcts)

            # Pass 2: outliers + % differ
            for row, sp, dp in valid_pairs:
                row["_warnings"].extend(self.verify_starting_price_outlier(sp, avg))
                if sp > 0:
                    lp = (Decimal(dp) * Decimal(100)) / Decimal(sp)
                    row["_warnings"].extend(
                        self.verify_lot_deposit_percent(lp, representative)
                    )
                    row["_lot_deposit_percent"] = str(quantize_lot_percent(lp))
                else:
                    row["_lot_deposit_percent"] = None

            # Build lot result rows for this project
            p_err = 0
            p_warn = 0
            for row in rows:
                errors = row["_errors"]
                warnings = row["_warnings"]
                if errors:
                    status = "ERROR"
                elif warnings:
                    status = "WARNING"
                else:
                    status = "VALID"
                p_err += len(errors)
                p_warn += len(warnings)

                # Sanitize amounts for display / re-apply
                sp_out = row["_sp"]
                dp_out = row["_dp"]
                # if invalid, keep original for display
                if sp_out is None and row.get("starting_price") not in (None, ""):
                    sp_display = row.get("starting_price")
                else:
                    sp_display = sp_out
                if dp_out is None and row.get("deposit_amount") not in (None, ""):
                    dp_display = row.get("deposit_amount")
                else:
                    dp_display = dp_out

                lot_results.append(
                    {
                        "row": row.get("row"),
                        "project_code": row.get("project_code"),
                        "lot_code": row.get("lot_code"),
                        "name": row.get("name"),
                        "description": row.get("description"),
                        "starting_price": sp_display if sp_out is not None else row.get("starting_price"),
                        "deposit_amount": dp_display if dp_out is not None else row.get("deposit_amount"),
                        "bid_step_vnd": row.get("bid_step_vnd"),
                        "area": row.get("area"),
                        "lot_deposit_percent": row.get("_lot_deposit_percent"),
                        "status": status,
                        "errors": errors,
                        "warnings": warnings,
                        # clean ints for apply when valid
                        "starting_price_int": sp_out,
                        "deposit_amount_int": dp_out,
                    }
                )

            total_error_count += p_err
            total_warning_count += p_warn
            grand_sp += total_sp
            grand_dp += total_dp
            grand_valid += len(valid_pairs)

            project_summaries.append(
                {
                    "project_code": project_code,
                    "totalLots": len(rows),
                    "validLots": len(valid_pairs),
                    "errorCount": p_err,
                    "warningCount": p_warn,
                    "totalStartingPrice": total_sp,
                    "totalDeposit": total_dp,
                    "projectDepositPercent": (
                        float(project_pct.quantize(Decimal("0.0001")))
                        if project_pct is not None
                        else None
                    ),
                    "projectDepositPercentRaw": (
                        str(project_pct.quantize(Decimal("0.0001")))
                        if project_pct is not None
                        else None
                    ),
                    "representativeDepositPercent": (
                        float(representative) if representative is not None else None
                    ),
                    "averageStartingPrice": (
                        float(avg.quantize(Decimal("1"))) if avg is not None else None
                    ),
                    "projectWarnings": project_warnings,
                    "projectErrors": [],
                }
            )

        # Flatten project warnings into row-less count for UI
        for ps in project_summaries:
            total_warning_count += len(ps.get("projectWarnings") or [])

        grand_pct = self.calculate_project_deposit_percent(grand_dp, grand_sp)

        # Overall representative: from all valid lot percents
        all_pcts: List[Decimal] = []
        for lr in lot_results:
            if lr.get("status") != "ERROR" and lr.get("lot_deposit_percent"):
                try:
                    all_pcts.append(Decimal(str(lr["lot_deposit_percent"])))
                except Exception:
                    pass
        overall_rep = self.determine_representative_deposit_percent(all_pcts)

        has_row_errors = any(r["status"] == "ERROR" for r in lot_results)
        can_continue = not has_row_errors

        return {
            "totalLots": len(self.lots),
            "errorCount": sum(len(r["errors"]) for r in lot_results),
            "warningCount": total_warning_count,
            "totalStartingPrice": grand_sp,
            "totalDeposit": grand_dp,
            "projectDepositPercent": (
                float(grand_pct.quantize(Decimal("0.0001"))) if grand_pct is not None else None
            ),
            "projectDepositPercentRaw": (
                str(grand_pct.quantize(Decimal("0.0001"))) if grand_pct is not None else None
            ),
            "representativeDepositPercent": (
                float(overall_rep) if overall_rep is not None else None
            ),
            "averageStartingPrice": None,
            "projectWarnings": [
                w
                for ps in project_summaries
                for w in (ps.get("projectWarnings") or [])
            ],
            "projectErrors": [],
            "projects": project_summaries,
            "lots": lot_results,
            "can_continue": can_continue,
            "has_errors": has_row_errors,
            "has_warnings": total_warning_count > 0,
        }


def verify_import_lots(lots: List[Dict[str, Any]]) -> Dict[str, Any]:
    return ProjectImportVerifier(lots).run()
