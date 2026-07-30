"""Enhance parser_service with PDF support via pdfplumber (optional)."""
from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import IO, List, Dict, Any


def parse_pdf_v2(file_obj: IO[bytes]) -> List[Dict[str, Any]]:
    """Parse a PDF bank statement. Requires `pdfplumber`.

    Heuristics: for each line, look for
      (date pattern) ... (description) ... (amount)
    Debits are negative, credits positive. Adjust regex per bank format.
    """
    try:
        import pdfplumber  # type: ignore
    except ImportError:
        from app.services.parser_service import StatementParseError
        raise StatementParseError(
            "PDF parsing requires `pdfplumber`. Install with: pip install pdfplumber"
        )

    from app.services.parser_service import StatementParseError

    txns: list[dict] = []
    date_re = re.compile(r"(\d{2}[-/]\d{2}[-/]\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4})")
    amt_re = re.compile(r"([-+]?[\d,]+\.\d{2})")

    with pdfplumber.open(file_obj) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.split("\n"):
                dm = date_re.search(line)
                am = amt_re.findall(line)
                if not dm or not am:
                    continue
                raw_date = dm.group(1)
                # last amount on the line = the transaction amount
                raw_amt = am[-1].replace(",", "")
                try:
                    amount = Decimal(raw_amt)
                except InvalidOperation:
                    continue
                parsed_date = _parse_date_flex(raw_date)
                if not parsed_date:
                    continue
                # description = whatever's between date and amount
                desc = line[dm.end():line.rfind(am[-1])].strip()
                if not desc:
                    continue
                txn_type = "credit" if amount >= 0 else "debit"
                txns.append({
                    "date": parsed_date,
                    "description": desc[:200],
                    "amount": abs(amount),
                    "type": txn_type,
                })
    if not txns:
        raise StatementParseError("Couldn't find transactions in the PDF. Try converting to CSV.")
    return txns


def _parse_date_flex(raw: str):
    for fmt in ("%d-%m-%Y","%d-%m-%y","%d/%m/%Y","%d/%m/%y","%Y-%m-%d",
                "%d %b %Y","%d %B %Y","%d %b %y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None
