"""Auto-categorizer — rule-based today, Gemini-pluggable tomorrow.

Usage:
    from app.services.categorizer_service import categorize
    result = categorize("SWIGGY BANGALORE", txn_type="debit")
    # result = {"category_name": "Dining", "kind": "expense"}

If a `GEMINI_API_KEY` env var is set, we'll (optionally) use Gemini for
descriptions that don't match any keyword rule. All routes call `categorize()`
— they never care which backend was used.
"""
from __future__ import annotations

import os
import re
from typing import Optional


# Keyword rules → (category_name, kind)
# `kind` is one of: "expense", "income", "transfer"
_RULES: list[tuple[re.Pattern, str, str]] = [
    # Income
    (re.compile(r"\bsalary|payroll|stipend\b", re.I), "Salary", "income"),
    (re.compile(r"\bfreelance|upwork|fiverr|contract\b", re.I), "Freelance", "income"),
    (re.compile(r"\binterest|dividend|coupon\b", re.I), "Interest", "income"),
    (re.compile(r"\brefund|reversal|cashback\b", re.I), "Refund", "income"),
    # Transfers
    (re.compile(r"\bupi transfer|neft|imps|rtgs|internal transfer|self transfer\b", re.I), "Transfer", "transfer"),
    # Dining
    (re.compile(r"\bswiggy|zomato|dominos|pizza|kfc|mcd|starbucks|cafe|restaurant|dine\b", re.I), "Dining", "expense"),
    # Grocery
    (re.compile(r"\bbigbasket|grofers|blinkit|dmart|reliance fresh|grocer|supermarket|kirana\b", re.I), "Grocery", "expense"),
    # Transportation
    (re.compile(r"\buber|ola|rapido|metro|irctc|indigo|spicejet|petrol|fuel|bpcl|hpcl|iocl\b", re.I), "Transportation", "expense"),
    # Utilities
    (re.compile(r"\belectricity|bescom|tneb|adani electric|torrent power\b", re.I), "Electricity", "expense"),
    (re.compile(r"\bwater bill|bwssb|jal board\b", re.I), "Water", "expense"),
    (re.compile(r"\bgas bill|indraprastha|mahanagar gas|igl\b", re.I), "Gas", "expense"),
    (re.compile(r"\bairtel|jio|vi\b|vodafone|bsnl|internet|broadband|act fibernet\b", re.I), "Internet", "expense"),
    (re.compile(r"\bmobile recharge|prepaid\b", re.I), "Phone Bill", "expense"),
    # Housing / EMI / Insurance
    (re.compile(r"\brent\b", re.I), "Rent", "expense"),
    (re.compile(r"\bemi|loan|hdfc bank loan|axis loan\b", re.I), "EMI", "expense"),
    (re.compile(r"\binsurance|lic|hdfc life|policy\b", re.I), "Insurance", "expense"),
    (re.compile(r"\bhospital|pharmacy|apollo|1mg|pharmeasy|clinic|dentist|medical\b", re.I), "Healthcare", "expense"),
    # Entertainment / Shopping
    (re.compile(r"\bnetflix|prime video|hotstar|spotify|youtube premium|jio cinema\b", re.I), "Subscriptions", "expense"),
    (re.compile(r"\bbookmyshow|pvr|inox|cinepolis|concert|event\b", re.I), "Entertainment", "expense"),
    (re.compile(r"\bamazon|flipkart|myntra|ajio|nykaa|meesho|shopping|mall\b", re.I), "Shopping", "expense"),
]


def categorize(description: str, txn_type: str) -> dict:
    """Return {'category_name': str, 'kind': 'expense'|'income'|'transfer'}."""
    desc = (description or "").strip()
    for pattern, name, kind in _RULES:
        if pattern.search(desc):
            return {"category_name": name, "kind": kind}

    # Try optional Gemini backend
    if os.environ.get("GEMINI_API_KEY"):
        result = _try_gemini(desc, txn_type)
        if result:
            return result

    # Fallback default based on transaction direction
    return {
        "category_name": "Miscellaneous",
        "kind": "income" if txn_type == "credit" else "expense",
    }


def _try_gemini(description: str, txn_type: str) -> Optional[dict]:
    """Best-effort Gemini classification. Silent-fails to None on any error."""
    try:
        from google import genai  # type: ignore
        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        prompt = (
            "You are a bank transaction categorizer. Return ONLY a JSON object "
            'like {"category":"Dining","kind":"expense"}. '
            "kind is one of: expense, income, transfer. "
            f'Transaction: "{description}" (type={txn_type}).'
        )
        resp = client.models.generate_content(
            model="gemini-3.6-flash", contents=prompt
        )
        import json
        raw = (resp.text or "").strip().strip("`")
        if raw.startswith("json"):
            raw = raw[4:].strip()
        data = json.loads(raw)
        cat = str(data.get("category", "")).strip()
        kind = str(data.get("kind", "")).strip().lower()
        if cat and kind in {"expense", "income", "transfer"}:
            return {"category_name": cat, "kind": kind}
    except Exception:
        return None
    return None
