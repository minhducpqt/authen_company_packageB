import pandas as pd

HEADER_MAP = {
    # Dates
    "Transaction Date": "txn_time",
    "Posting Date": "txn_time",
    "Ngày giao dịch": "txn_time",
    "Ngày hạch toán": "txn_time",
    # Desc
    "Description": "description",
    "Nội dung": "description",
    "Remark": "description",
    "Details": "description",
    # Amounts
    "Withdrawal": "debit",
    "Debit": "debit",
    "Số tiền rút": "debit",
    "Deposit": "credit",
    "Credit": "credit",
    "Số tiền vào": "credit",
    # Balance
    "Balance": "balance_after",
    "Số dư": "balance_after",
    # Ref
    "Ref No": "ref_no",
    "Reference": "ref_no",
}

def normalize_headers(df: pd.DataFrame) -> pd.DataFrame:
    new_cols = []
    for c in df.columns:
        clean = str(c).strip()
        new_cols.append(HEADER_MAP.get(clean, clean))
    df.columns = new_cols
    return df
