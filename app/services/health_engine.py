"""Financial Health Score engine (0–100).

Weights (from spec):
    - Emergency Fund Ratio         (30 pts)
    - Savings Rate                 (20 pts)
    - Debt-to-Income (DTI) ratio   (25 pts)  — proxied via EMI category spend
    - Investment Ratio             (10 pts)  — assets vs cash
    - Budget Discipline / Variance (15 pts)

Nothing is stored — this is computed on-demand from live data.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal
from typing import Iterable

from app.models import Account, Asset, Expense, Income, Budget, Category


def _to_float(v) -> float:
    return float(v or 0)


def _sum(items: Iterable, attr: str) -> float:
    return float(sum((getattr(i, attr) or 0) for i in items))


def compute_health_score(user, *, today: date | None = None) -> dict:
    """Return a breakdown dict with 5 sub-scores + total (0–100)."""
    today = today or date.today()
    month_start = today.replace(day=1)

    accounts = list(user.accounts)
    assets = list(user.assets)

    # ---------- income & expenses this month ----------
    incomes_this_month = [
        i for i in user.__dict__.get("_income_this_month", []) or _query_income(user, month_start, today)
    ]
    expenses_this_month = list(_query_expenses(user, month_start, today))

    monthly_income = _sum(incomes_this_month, "amount")
    if monthly_income == 0 and user.profile:
        monthly_income = _to_float(user.profile.monthly_gross_income)

    monthly_expenses = _sum(expenses_this_month, "amount")

    # ---------- emergency fund (liquid cash across accounts + cash-type assets) ----------
    liquid = _sum(accounts, "current_balance") + sum(
        _to_float(a.current_value) for a in assets if a.asset_type in ("cash", "fixed_deposit")
    )
    ef_months = (liquid / monthly_expenses) if monthly_expenses > 0 else (6 if liquid > 0 else 0)
    # 6+ months -> full 30 pts. Linear below.
    ef_score = round(min(30.0, (ef_months / 6.0) * 30.0), 1)

    # ---------- savings rate ----------
    savings_rate = 0.0
    if monthly_income > 0:
        savings_rate = max(0.0, (monthly_income - monthly_expenses) / monthly_income)
    # 30%+ savings -> full 20 pts
    savings_score = round(min(20.0, (savings_rate / 0.30) * 20.0), 1)

    # ---------- DTI (EMI spend / income) ----------
    emi_spent = sum(
        _to_float(e.amount) for e in expenses_this_month
        if e.category and e.category.name.lower() == "emi"
    )
    dti = (emi_spent / monthly_income) if monthly_income > 0 else 0.0
    # 0% -> 25 pts, 40%+ -> 0 pts (linear)
    dti_score = round(max(0.0, min(25.0, (1 - dti / 0.40) * 25.0)), 1)

    # ---------- investment ratio ----------
    invested = sum(
        _to_float(a.current_value) for a in assets
        if a.asset_type in ("stocks", "mutual_funds", "gold", "crypto", "property")
    )
    total_wealth = invested + liquid
    inv_ratio = (invested / total_wealth) if total_wealth > 0 else 0.0
    # 40%+ invested -> full 10 pts
    inv_score = round(min(10.0, (inv_ratio / 0.40) * 10.0), 1)

    # ---------- budget discipline ----------
    budgets = _query_budgets(user, today.month, today.year)
    total_budget = _sum(budgets, "budgeted_amount")
    variance_score = 15.0
    if total_budget > 0:
        overshoot = max(0.0, monthly_expenses - total_budget)
        # 0% over -> 15 pts, 30%+ over -> 0 pts
        pct_over = overshoot / total_budget
        variance_score = round(max(0.0, min(15.0, (1 - pct_over / 0.30) * 15.0)), 1)

    total = round(ef_score + savings_score + dti_score + inv_score + variance_score, 1)

    return {
        "total": total,
        "grade": _grade(total),
        "components": {
            "emergency_fund": {"score": ef_score, "max": 30, "months": round(ef_months, 1)},
            "savings_rate": {"score": savings_score, "max": 20, "rate_pct": round(savings_rate * 100, 1)},
            "dti": {"score": dti_score, "max": 25, "ratio_pct": round(dti * 100, 1)},
            "investment_ratio": {"score": inv_score, "max": 10, "ratio_pct": round(inv_ratio * 100, 1)},
            "budget_discipline": {"score": variance_score, "max": 15, "monthly_expenses": monthly_expenses, "total_budget": total_budget},
        },
        "monthly_income": monthly_income,
        "monthly_expenses": monthly_expenses,
    }


def compute_net_worth(user) -> dict:
    """Sum of account balances + asset values. Debts aren't tracked separately yet."""
    accounts_total = _sum(user.accounts, "current_balance")
    assets_total = _sum(user.assets, "current_value")
    return {
        "accounts_total": accounts_total,
        "assets_total": assets_total,
        "net_worth": accounts_total + assets_total,
    }


def _grade(total: float) -> str:
    if total >= 85: return "Excellent"
    if total >= 70: return "Good"
    if total >= 50: return "Fair"
    if total >= 30: return "Needs work"
    return "Critical"


# ---------- data-access helpers (kept tiny to avoid tight-coupling) ----------

def _query_expenses(user, start: date, end: date):
    return Expense.query.filter(
        Expense.user_id == user.id,
        Expense.date >= start,
        Expense.date <= end,
    ).all()


def _query_income(user, start: date, end: date):
    return Income.query.filter(
        Income.user_id == user.id,
        Income.date >= start,
        Income.date <= end,
    ).all()


def _query_budgets(user, month: int, year: int):
    return Budget.query.filter(
        Budget.user_id == user.id,
        Budget.month == month,
        Budget.year == year,
    ).all()
