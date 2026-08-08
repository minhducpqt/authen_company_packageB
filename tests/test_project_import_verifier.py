# tests/test_project_import_verifier.py
"""Unit tests — ProjectImportVerifier (Service B preview)."""
from __future__ import annotations

from decimal import Decimal

from utils.project_import_verifier import (
    ProjectImportVerifier,
    CODE_DEPOSIT_GREATER_THAN_STARTING_PRICE,
    CODE_DEPOSIT_PERCENT_DIFFERS_FROM_PROJECT,
    CODE_DEPOSIT_TOO_HIGH,
    CODE_DEPOSIT_TOO_LOW,
    CODE_INVALID_DEPOSIT,
    CODE_INVALID_STARTING_PRICE,
    CODE_STARTING_PRICE_OUTLIER,
    CODE_STARTING_PRICE_TOO_HIGH,
    CODE_STARTING_PRICE_TOO_LOW,
    CODE_UNUSUAL_PROJECT_DEPOSIT_PERCENT,
    is_round_project_percent,
    is_strict_non_negative_integer,
)


def _lot(row, sp, dp, code="L1", project="P1"):
    return {
        "row": row,
        "project_code": project,
        "lot_code": code,
        "name": f"Lot {code}",
        "starting_price": sp,
        "deposit_amount": dp,
    }


def _codes(issues):
    return {i["code"] for i in issues}


def test_starting_price_not_integer():
    r = ProjectImportVerifier([_lot(2, 100.5, 20_000_000)]).run()
    lot = r["lots"][0]
    assert lot["status"] == "ERROR"
    assert CODE_INVALID_STARTING_PRICE in _codes(lot["errors"])
    assert r["has_errors"] is True
    assert r["can_continue"] is False


def test_deposit_not_integer():
    r = ProjectImportVerifier([_lot(2, 100_000_000, "20.5")]).run()
    lot = r["lots"][0]
    assert lot["status"] == "ERROR"
    assert CODE_INVALID_DEPOSIT in _codes(lot["errors"])


def test_deposit_greater_than_starting_warning():
    r = ProjectImportVerifier([_lot(2, 10_000_000, 20_000_000)]).run()
    lot = r["lots"][0]
    assert lot["status"] == "WARNING"
    assert CODE_DEPOSIT_GREATER_THAN_STARTING_PRICE in _codes(lot["warnings"])
    assert r["can_continue"] is True


def test_amounts_below_one_million():
    r = ProjectImportVerifier([_lot(2, 500_000, 100_000)]).run()
    lot = r["lots"][0]
    assert CODE_STARTING_PRICE_TOO_LOW in _codes(lot["warnings"])
    assert CODE_DEPOSIT_TOO_LOW in _codes(lot["warnings"])


def test_amounts_above_100_billion():
    big = 100_000_000_001
    r = ProjectImportVerifier([_lot(2, big, big)]).run()
    lot = r["lots"][0]
    assert CODE_STARTING_PRICE_TOO_HIGH in _codes(lot["warnings"])
    assert CODE_DEPOSIT_TOO_HIGH in _codes(lot["warnings"])


def test_starting_price_outlier_high():
    lots = [_lot(i, 10_000_000, 2_000_000, f"A{i}") for i in range(2, 22)]
    lots.append(_lot(50, 2_000_000_000, 400_000_000, "OUT"))
    r = ProjectImportVerifier(lots).run()
    out = next(x for x in r["lots"] if x["lot_code"] == "OUT")
    assert CODE_STARTING_PRICE_OUTLIER in _codes(out["warnings"])


def test_starting_price_outlier_low():
    lots = [_lot(i, 500_000_000, 100_000_000, f"A{i}") for i in range(2, 22)]
    lots.append(_lot(50, 1_000_000, 200_000, "LOW"))
    r = ProjectImportVerifier(lots).run()
    low = next(x for x in r["lots"] if x["lot_code"] == "LOW")
    assert CODE_STARTING_PRICE_OUTLIER in _codes(low["warnings"])


def test_project_deposit_percent_20_no_unusual_warning():
    # 20% exact
    lots = [_lot(i, 100_000_000, 20_000_000, f"L{i}") for i in range(2, 7)]
    r = ProjectImportVerifier(lots).run()
    assert not any(
        w["code"] == CODE_UNUSUAL_PROJECT_DEPOSIT_PERCENT for w in r["projectWarnings"]
    )
    assert abs(r["projectDepositPercent"] - 20.0) < 0.001


def test_project_deposit_percent_unusual():
    # total sp = 100M, deposit = 18_222_200 → 18.2222%
    lots = [_lot(2, 100_000_000, 18_222_200, "L1")]
    r = ProjectImportVerifier(lots).run()
    assert any(w["code"] == CODE_UNUSUAL_PROJECT_DEPOSIT_PERCENT for w in r["projectWarnings"])
    assert is_round_project_percent(Decimal("20")) is True
    assert is_round_project_percent(Decimal("18.2222")) is False


def test_representative_percent_majority_differs():
    lots = [_lot(i, 100_000_000, 20_000_000, f"A{i}") for i in range(2, 12)]  # 10 x 20%
    lots.append(_lot(20, 100_000_000, 30_000_000, "B30"))  # 30%
    lots.append(_lot(21, 100_000_000, 18_000_000, "C18"))
    r = ProjectImportVerifier(lots).run()
    assert r["representativeDepositPercent"] == 20.0
    b30 = next(x for x in r["lots"] if x["lot_code"] == "B30")
    assert CODE_DEPOSIT_PERCENT_DIFFERS_FROM_PROJECT in _codes(b30["warnings"])
    msg = " ".join(w["message"] for w in b30["warnings"])
    assert "30" in msg and "20" in msg


def test_one_row_multiple_warnings():
    # deposit > starting, both < 1M
    r = ProjectImportVerifier([_lot(2, 500_000, 800_000)]).run()
    lot = r["lots"][0]
    assert lot["status"] == "WARNING"
    assert len(lot["warnings"]) >= 3  # greater + both too low (maybe more)


def test_preview_with_error_still_full_data():
    lots = [
        _lot(2, 100_000_000, 20_000_000, "OK"),
        _lot(3, 99.5, 20_000_000, "BAD"),
    ]
    r = ProjectImportVerifier(lots).run()
    assert r["totalLots"] == 2
    assert len(r["lots"]) == 2
    assert r["has_errors"] is True
    assert r["can_continue"] is False
    assert r["lots"][0]["lot_code"] == "OK"
    assert r["lots"][1]["status"] == "ERROR"


def test_warnings_only_allows_continue():
    lots = [_lot(2, 10_000_000, 3_000_000)]  # 30% ok whole; deposit < starting
    # may get percent differ if alone — still continue
    r = ProjectImportVerifier(lots).run()
    assert r["has_errors"] is False
    assert r["can_continue"] is True


def test_integer_helpers():
    assert is_strict_non_negative_integer(10)
    assert is_strict_non_negative_integer(10.0)
    assert not is_strict_non_negative_integer(10.5)
    assert not is_strict_non_negative_integer("x")
