from __future__ import annotations
from typing import List
from .base_parser import ParseResult, BankStatementParser
from .parsers.woori_xls import WooriXlsParser

PARSERS: List[BankStatementParser] = [
    WooriXlsParser(),
]

def sniff_and_parse(file_bytes: bytes, filename: str) -> ParseResult:
    for p in PARSERS:
        if p.can_parse(file_bytes, filename):
            return p.parse(file_bytes)
    return {"ok": False, "rows": [], "errors": ["Không tìm thấy parser phù hợp"], "row_errors": []}
