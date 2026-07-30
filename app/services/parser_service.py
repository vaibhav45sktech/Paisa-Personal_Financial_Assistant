"""CSV/PDF bank statement parser — no Flask, no DB.

Adapted from the standalone `parser.py` MVP the user shared. Returns a list of
normalised transaction dicts:
    {"date": date, "description": str, "amount": Decimal, "type": "credit"|"debit"}

PDF support is stubbed with a friendly error until `pdfplumber` is installed.
"""
from __future__ import annotations

import csv
import re
from datetime import datetime, date as date_cls
from decimal import Decimal, InvalidOperation
from typing import IO, List, Dict, Any


class StatementParseError(Exception):
    """Raised when the uploaded statement cannot be parsed."""


# ---------- public entry points ----------

def parse_csv(file_obj: IO[bytes] | IO[str]) -> List[Dict[str, Any]]:
    """Parse a CSV bank statement.

    Supports either:
        1. Date, Description, Amount   (signed: positive=credit, negative=debit)
        2. Date, Description, Debit, Credit [, Balance]
    """
    try:
        text = _read_text(file_obj)
    except UnicodeDecodeError as exc:
        raise StatementParseError(
            "Could not decode the file — please upload a valid UTF-8 CSV."
        ) from exc

    try:
        reader = csv.DictReader(text.splitlines())
    except csv.Error as exc:
        raise StatementParseError(f"Malformed CSV: {exc}")

    if not reader.fieldnames:
        raise StatementParseError("The CSV file appears to be empty.")

    fields = {f.strip() for f in reader.fieldnames}
    has_amount = "Amount" in fields
    has_debit_credit = {"Debit", "Credit"}.issubset(fields)
    if not {"Date", "Description"}.issubset(fields):
        raise StatementParseError("CSV must include 'Date' and 'Description' columns.")
    if not (has_amount or has_debit_credit):
        raise StatementParseError(
            "CSV must include either an 'Amount' column, or both 'Debit' and 'Credit' columns."
        )

    txns: List[Dict[str, Any]] = []
    for row_number, row in enumerate(reader, start=2):
        txn = _parse_row(row, row_number, has_amount)
        if txn:
            txns.append(txn)

    if not txns:
        raise StatementParseError("No transactions were found in the uploaded file.")
    return txns


def parse_pdf(file_obj: IO[bytes]) -> List[Dict[str, Any]]:
    """PDF parser stub — enable by installing `pdfplumber` and implementing here."""
    raise StatementParseError(
        "PDF parsing isn't enabled yet. Please upload a CSV statement for now."
    )


# ---------- helpers ----------

def _read_text(file_obj) -> str:
    data = file_obj.read()
    if isinstance(data, bytes):
        for enc in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                return data.decode(enc)
            except UnicodeDecodeError:
                continue
        raise UnicodeDecodeError("all", data, 0, 1, "unknown encoding")
    return data


def _parse_row(row: dict, row_number: int, has_amount: bool):
    raw_date = (row.get("Date") or "").strip()
    raw_desc = (row.get("Description") or "").strip()

    if has_amount:
        raw_amount = (row.get("Amount") or "").strip()
        if not raw_date and not raw_desc and not raw_amount:
            return None
        amount_value = _clean_amount(raw_amount)
        if amount_value is None:
            raise StatementParseError(f"Row {row_number}: invalid amount '{raw_amount}'.")
    else:
        raw_debit = (row.get("Debit") or "").strip()
        raw_credit = (row.get("Credit") or "").strip()
        if not raw_date and not raw_desc and not raw_debit and not raw_credit:
            return None
        debit = _clean_amount(raw_debit) or Decimal("0")
        credit = _clean_amount(raw_credit) or Decimal("0")
        if debit == 0 and credit == 0:
            return None  # opening balance rows etc.
        amount_value = credit - debit

    parsed_date = _parse_date(raw_date)
    if parsed_date is None:
        raise StatementParseError(f"Row {row_number}: invalid date '{raw_date}'.")
    if not raw_desc:
        raise StatementParseError(f"Row {row_number}: description is missing.")

    txn_type = "credit" if amount_value >= 0 else "debit"
    return {
        "date": parsed_date,
        "description": raw_desc,
        "amount": abs(amount_value),
        "type": txn_type,
    }


def _clean_amount(raw: str):
    if not raw:
        return None
    cleaned = re.sub(r"[^\d.\-]", "", raw)
    if cleaned in ("", "-", "."):
        return None
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def _parse_date(raw: str):
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%Y", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None
