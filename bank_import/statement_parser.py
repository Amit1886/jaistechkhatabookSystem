from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Iterable


@dataclass(frozen=True)
class BankTxn:
    date: str
    description: str
    debit: Decimal
    credit: Decimal
    balance: Decimal | None = None
    raw: dict[str, Any] | None = None


def _to_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value).replace(",", "").strip())
    except Exception:
        return Decimal("0.00")


def _parse_date(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%b-%Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except Exception:
            pass
    return value


def parse_bank_statement_csv(file_bytes: bytes, *, encoding: str = "utf-8") -> list[BankTxn]:
    """
    Parses CSV statements with flexible column names:
    date, description/narration, debit, credit, amount, balance.
    """
    # Handle UTF-8 BOM automatically
    if encoding.lower() in {"utf-8", "utf8"} and file_bytes.startswith(b"\xef\xbb\xbf"):
        encoding = "utf-8-sig"
    text = file_bytes.decode(encoding, errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    txns: list[BankTxn] = []
    for row in reader:
        if not row:
            continue
        keys = {k.lower().strip(): k for k in row.keys() if k}
        date_key = keys.get("date") or keys.get("txn date") or keys.get("transaction date")
        desc_key = keys.get("description") or keys.get("narration") or keys.get("details") or keys.get("particulars")
        debit_key = keys.get("debit") or keys.get("withdrawal") or keys.get("dr")
        credit_key = keys.get("credit") or keys.get("deposit") or keys.get("cr")
        amount_key = keys.get("amount")
        balance_key = keys.get("balance") or keys.get("closing balance")

        d = _parse_date(row.get(date_key, "") if date_key else "")
        desc = str(row.get(desc_key, "") if desc_key else "").strip()

        debit = _to_decimal(row.get(debit_key, "") if debit_key else "")
        credit = _to_decimal(row.get(credit_key, "") if credit_key else "")
        if debit == 0 and credit == 0 and amount_key:
            amt = _to_decimal(row.get(amount_key, ""))
            # Heuristic: negative is debit, positive is credit
            if amt < 0:
                debit = abs(amt)
            else:
                credit = amt

        bal = None
        if balance_key:
            b = _to_decimal(row.get(balance_key, ""))
            bal = b

        txns.append(BankTxn(date=d, description=desc, debit=debit, credit=credit, balance=bal, raw=row))
    return txns


def parse_bank_statement_xlsx(file_bytes: bytes) -> list[BankTxn]:
    """
    Minimal XLSX parser (requires openpyxl). Attempts to infer common columns.
    """
    try:
        import openpyxl  # type: ignore
    except Exception as e:
        raise RuntimeError("XLSX support requires openpyxl") from e

    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    header = [str(c or "").strip() for c in rows[0]]
    key_map = {h.lower(): idx for idx, h in enumerate(header) if h}

    def _col(*names: str) -> int | None:
        for n in names:
            if n.lower() in key_map:
                return key_map[n.lower()]
        return None

    date_i = _col("date", "txn date", "transaction date")
    desc_i = _col("description", "narration", "details", "particulars")
    debit_i = _col("debit", "withdrawal", "dr")
    credit_i = _col("credit", "deposit", "cr")
    amount_i = _col("amount")
    bal_i = _col("balance", "closing balance")

    out: list[BankTxn] = []
    for r in rows[1:]:
        if not r:
            continue
        date_v = str(r[date_i] or "").strip() if date_i is not None and date_i < len(r) else ""
        desc_v = str(r[desc_i] or "").strip() if desc_i is not None and desc_i < len(r) else ""
        debit_v = _to_decimal(r[debit_i] if debit_i is not None and debit_i < len(r) else "")
        credit_v = _to_decimal(r[credit_i] if credit_i is not None and credit_i < len(r) else "")
        if debit_v == 0 and credit_v == 0 and amount_i is not None and amount_i < len(r):
            amt = _to_decimal(r[amount_i])
            if amt < 0:
                debit_v = abs(amt)
            else:
                credit_v = amt
        bal_v = None
        if bal_i is not None and bal_i < len(r):
            bal_v = _to_decimal(r[bal_i])
        out.append(
            BankTxn(
                date=_parse_date(date_v),
                description=desc_v,
                debit=debit_v,
                credit=credit_v,
                balance=bal_v,
                raw={"row": list(r)},
            )
        )
    return out


def parse_bank_statement(file_obj) -> list[BankTxn]:
    """
    Dispatch based on file extension.
    """
    name = str(getattr(file_obj, "name", "") or "").lower()
    file_bytes = file_obj.read() if hasattr(file_obj, "read") else b""
    if name.endswith(".xlsx"):
        return parse_bank_statement_xlsx(file_bytes)
    return parse_bank_statement_csv(file_bytes)
