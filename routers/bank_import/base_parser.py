from __future__ import annotations
from typing import TypedDict, List, Dict, Any, Protocol

class ParseResult(TypedDict, total=False):
    ok: bool
    rows: List[Dict[str, Any]]
    errors: List[str]
    row_errors: List[Dict[str, Any]]

class BankStatementParser(Protocol):
    def can_parse(self, file_bytes: bytes, filename: str) -> bool: ...
    def parse(self, file_bytes: bytes) -> ParseResult: ...
