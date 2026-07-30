"""Dashboard aggregates — actual-vs-budget, net worth, monthly summaries.

Every function is idempotent and returns plain dicts/lists so templates can
render without touching the ORM directly.
"""
from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import date
from decimal import Decimal

from app.models import Expense, Income, Budget, Category
from app.extensions import db


def actual_vs_budget(user, month: int, year: int) -> list[dict]:
    """Compare each budgeted category to actual spend that month.

    Returns rows sorted by budgeted amount desc:
        [{"category": "Grocery", "budgeted": 8000, "actual": 7250, "pct": 90.6, "status": "warning", "color": "#F97316"}]
    """
    # Actuals: sum expenses per category for the month
    last_day = monthrange(year, month)[1]
    start = date(year, month, 1)
    end = date(year, month, last_day)

    actuals_q = (
        db.session.query(Expense.category_id, db.func.coalesce(db.func.sum(Expense.amount), 0))
        .filter(
            Expense.user_id == user.id,
            Expense.date >= start,
            Expense.date <= end,
        )
        .group_by(Expense.category_id)
        .all()
    )
    actuals = {row[0]: float(row[1]) for row in actuals_q}

    # Budgets: one row per category for this month
    budgets = (
        Budget.query.filter(Budget.user_id == user.id, Budget.month == month, Budget.year == year)
        .join(Category, Category.id == Budget.category_id)
        .all()
    )

    rows = []
    for b in budgets:
        budgeted = float(b.budgeted_amount or 0)
        actual = actuals.pop(b.category_id, 0.0)
        pct = (actual / budgeted * 100) if budgeted > 0 else 0
        status = _bucket(pct)
        rows.append({
            "category": b.category.name,
            "color": b.category.color or "#78716C",
            "icon": b.category.icon or "bi-tag",
            "budgeted": budgeted,
            "actual": actual,
            "pct": round(pct, 1),
            "status": status,
        })

    # Actuals with no budget still shown (over-spent categories the user forgot to budget)
    for cat_id, amount in actuals.items():
        if amount <= 0:
            continue
        cat = db.session.get(Category, cat_id) if cat_id else None
        rows.append({
            "category": cat.name if cat else "Uncategorised",
            "color": (cat.color if cat else None) or "#78716C",
            "icon": (cat.icon if cat else None) or "bi-tag",
            "budgeted": 0,
            "actual": amount,
            "pct": 0,
            "status": "no_budget",
        })

    rows.sort(key=lambda r: (r["budgeted"] == 0, -r["budgeted"], -r["actual"]))
    return rows


def _bucket(pct: float) -> str:
    if pct == 0: return "unused"
    if pct < 80: return "ok"
    if pct <= 100: return "warning"
    return "over"


def monthly_totals(user, month: int, year: int) -> dict:
    last_day = monthrange(year, month)[1]
    start = date(year, month, 1)
    end = date(year, month, last_day)
    inc = db.session.query(db.func.coalesce(db.func.sum(Income.amount), 0)).filter(
        Income.user_id == user.id, Income.date >= start, Income.date <= end
    ).scalar() or 0
    exp = db.session.query(db.func.coalesce(db.func.sum(Expense.amount), 0)).filter(
        Expense.user_id == user.id, Expense.date >= start, Expense.date <= end
    ).scalar() or 0
    return {"income": float(inc), "expenses": float(exp), "savings": float(inc) - float(exp)}
