"""Statement ingestion pipeline — parse → save Transactions → auto-categorize → confirm."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import IO

from app.extensions import db
from app.models import (
    BankStatement, Transaction, Category, Expense, Income, Account,
)
from app.services import parser_service, categorizer_service


def import_csv(user, account: Account, file_obj: IO, filename: str) -> BankStatement:
    """Parse the CSV, save raw Transactions with auto-categories, mark statement processed."""
    stmt = BankStatement(
        user_id=user.id,
        account_id=account.id,
        filename=filename,
        status="pending",
        total_records_extracted=0,
    )
    db.session.add(stmt)
    db.session.flush()  # get stmt.id

    try:
        rows = parser_service.parse_csv(file_obj)
    except parser_service.StatementParseError:
        stmt.status = "failed"
        db.session.commit()
        raise

    # Preload user's categories for O(1) name -> id lookup
    cat_index = _category_index(user)

    for r in rows:
        result = categorizer_service.categorize(r["description"], r["type"])
        category = _get_or_create_category(user, result["category_name"], _kind_to_type(result["kind"]), cat_index)

        txn = Transaction(
            user_id=user.id,
            account_id=account.id,
            statement_id=stmt.id,
            category_id=category.id if category else None,
            date=r["date"],
            description=r["description"],
            merchant=r["description"][:120],
            amount=r["amount"],
            transaction_type=r["type"],
            is_expense=(result["kind"] == "expense"),
            is_income=(result["kind"] == "income"),
            is_transfer=(result["kind"] == "transfer"),
            status="unreviewed",
        )
        db.session.add(txn)

    stmt.status = "processed"
    stmt.total_records_extracted = len(rows)
    db.session.commit()
    return stmt


def confirm_transactions(user, txn_ids: list[str]) -> dict:
    """Move selected transactions from unreviewed → confirmed and create Expense/Income rows."""
    txns = (
        Transaction.query
        .filter(Transaction.user_id == user.id, Transaction.id.in_(txn_ids))
        .all()
    )
    created_expenses = 0
    created_income = 0
    for t in txns:
        if t.status == "confirmed":
            continue
        if t.is_expense:
            db.session.add(Expense(
                user_id=user.id, account_id=t.account_id, transaction_id=t.id,
                category_id=t.category_id, description=t.description,
                amount=t.amount, date=t.date,
            ))
            # decrement balance
            t.account.current_balance = (t.account.current_balance or Decimal(0)) - t.amount
            created_expenses += 1
        elif t.is_income:
            db.session.add(Income(
                user_id=user.id, account_id=t.account_id, transaction_id=t.id,
                source=t.description, amount=t.amount, date=t.date,
            ))
            t.account.current_balance = (t.account.current_balance or Decimal(0)) + t.amount
            created_income += 1
        # transfers don't affect net worth — no ledger row
        t.status = "confirmed"

    db.session.commit()
    return {"expenses": created_expenses, "income": created_income}


def ignore_transactions(user, txn_ids: list[str]) -> int:
    q = Transaction.query.filter(
        Transaction.user_id == user.id, Transaction.id.in_(txn_ids)
    )
    count = 0
    for t in q:
        t.status = "ignored"
        count += 1
    db.session.commit()
    return count


def update_transaction(user, txn_id: str, *, category_id: str | None = None,
                        kind: str | None = None) -> Transaction:
    """Let user re-classify a transaction before confirming."""
    t = Transaction.query.filter_by(id=txn_id, user_id=user.id).first_or_404()
    if category_id:
        t.category_id = category_id
    if kind:
        t.is_expense = (kind == "expense")
        t.is_income = (kind == "income")
        t.is_transfer = (kind == "transfer")
    db.session.commit()
    return t


# ---------- helpers ----------

def _kind_to_type(kind: str) -> str:
    return {"expense": "expense", "income": "income", "transfer": "transfer"}.get(kind, "expense")


def _category_index(user) -> dict:
    """Lookup dict keyed by (user_id_or_None, lower(name))."""
    cats = Category.query.filter(
        (Category.user_id == user.id) | (Category.user_id.is_(None))
    ).all()
    return {(c.user_id, c.name.lower()): c for c in cats}


def _get_or_create_category(user, name: str, type_: str, index: dict) -> Category | None:
    key_user = (user.id, name.lower())
    key_global = (None, name.lower())
    if key_user in index:
        return index[key_user]
    if key_global in index:
        return index[key_global]
    # Create user-scoped category on the fly
    cat = Category(user_id=user.id, name=name, type=type_)
    db.session.add(cat)
    db.session.flush()
    index[key_user] = cat
    return cat


def seed_default_categories(user) -> int:
    """Insert DEFAULT_CATEGORIES for a brand-new user. Idempotent."""
    from app.models import DEFAULT_CATEGORIES
    existing = {c.name.lower() for c in Category.query.filter_by(user_id=user.id).all()}
    added = 0
    for name, type_, icon, color in DEFAULT_CATEGORIES:
        if name.lower() in existing:
            continue
        db.session.add(Category(
            user_id=user.id, name=name, type=type_, icon=icon, color=color,
        ))
        added += 1
    if added:
        db.session.commit()
    return added
