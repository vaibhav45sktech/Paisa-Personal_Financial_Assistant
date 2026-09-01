"""Assembles the deterministic financial snapshot every engine reads from.

One place computes the raw metrics — surplus, EMI burden, emergency-fund
runway, savings rate, goal pressure — so the health score, the priority engine
and the explanation layer can never disagree about the numbers.

Every read is consent-gated. A revoked category yields `None` for the metrics
that depend on it, and the dependent rules are skipped rather than guessed.

Only money data is used here. No protected characteristic is read, stored or
scored — see DECISION_FACTORS below for the complete list of inputs.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date

from app.extensions import db
from app.models import Expense, Income, Budget, Category
from app.services import consent_service, health_engine

HEALTH_PURPOSE = "financial_health_analysis"

# Months of expenses a fully-funded emergency fund should cover.
EMERGENCY_FUND_TARGET_MONTHS = 6.0
# Savings-rate floor before we flag it.
HEALTHY_SAVINGS_RATE = 0.20
# EMI-to-income thresholds.
EMI_STRETCHED = 0.36
EMI_SEVERE = 0.50

# Rendered verbatim in the "Decision factors" panel so a user can audit exactly
# what the recommendation was built from.
DECISION_FACTORS = [
    ("Monthly income", "income"),
    ("Monthly expenses", "expenses"),
    ("Existing EMI commitments", "liabilities"),
    ("Liquid savings & account balances", "accounts"),
    ("Assets & investments", "assets"),
    ("Budget adherence", "expenses"),
    ("Savings goals", "goals"),
]

EXCLUDED_FACTORS = [
    "Caste", "Religion", "Gender", "Race or ethnicity",
    "Political affiliation", "Disability", "Health information",
    "Sexual orientation", "Age", "Marital status",
]


def _month_bounds(today: date) -> tuple[date, date]:
    return date(today.year, today.month, 1), date(
        today.year, today.month, monthrange(today.year, today.month)[1]
    )


def _category_spend(user, name: str, start: date, end: date) -> float:
    """Sum of this month's expenses in one named category."""
    total = (
        db.session.query(db.func.coalesce(db.func.sum(Expense.amount), 0))
        .join(Category, Category.id == Expense.category_id)
        .filter(
            Expense.user_id == user.id,
            Expense.date >= start,
            Expense.date <= end,
            db.func.lower(Category.name) == name.lower(),
        )
        .scalar()
    )
    return float(total or 0)


def build_context(user, *, today: date | None = None) -> dict:
    """Return the full deterministic snapshot, honouring consent throughout."""
    today = today or date.today()
    start, end = _month_bounds(today)

    def allowed(category: str) -> bool:
        return consent_service.has_consent(user.id, category, HEALTH_PURPOSE)

    granted = consent_service.granted_categories(user.id, HEALTH_PURPOSE)
    missing = consent_service.missing_categories(user.id, HEALTH_PURPOSE)

    # ---- income -----------------------------------------------------------
    monthly_income = None
    income_source = None
    if allowed("income"):
        logged = (
            db.session.query(db.func.coalesce(db.func.sum(Income.amount), 0))
            .filter(Income.user_id == user.id, Income.date >= start, Income.date <= end)
            .scalar()
        )
        monthly_income = float(logged or 0)
        income_source = "logged"
        # Mirror health_engine: fall back to the stated profile income so a
        # user who has onboarded but not yet imported a statement still gets
        # a usable read.
        if monthly_income == 0 and allowed("profile") and user.profile:
            monthly_income = float(user.profile.monthly_gross_income or 0)
            income_source = "profile"

    # ---- expenses ---------------------------------------------------------
    monthly_expenses = None
    expenses_source = None
    if allowed("expenses"):
        logged = (
            db.session.query(db.func.coalesce(db.func.sum(Expense.amount), 0))
            .filter(Expense.user_id == user.id, Expense.date >= start, Expense.date <= end)
            .scalar()
        )
        monthly_expenses = float(logged or 0)
        if monthly_expenses > 0:
            expenses_source = "logged"
        elif allowed("profile") and user.profile and user.profile.total_budget > 0:
            # Nothing logged yet — reason about the planned budget instead, so a
            # freshly-onboarded user still gets advice. Flagged, never silent.
            monthly_expenses = float(user.profile.total_budget)
            expenses_source = "budget"
        else:
            # Genuinely no expense data. Zero spending is not the same as
            # frugal spending, and must never be scored as if it were.
            expenses_source = None

    # ---- EMI / debt service ----------------------------------------------
    monthly_emi = _category_spend(user, "EMI", start, end) if allowed("liabilities") else None
    # A profile budget line for EMI is the fallback when nothing is logged.
    if (
        monthly_emi == 0
        and allowed("liabilities") and allowed("profile")
        and user.profile
    ):
        monthly_emi = float(user.profile.budget_map.get("EMI", 0) or 0)

    insurance_spend = (
        _category_spend(user, "Insurance", start, end) if allowed("expenses") else None
    )

    # ---- liquid savings & investments ------------------------------------
    liquid_savings = None
    if allowed("accounts"):
        liquid_savings = float(
            sum(float(a.current_balance or 0) for a in user.accounts)
        )
        if allowed("assets"):
            liquid_savings += sum(
                float(a.current_value or 0) for a in user.assets
                if a.asset_type in ("cash", "fixed_deposit")
            )

    invested = None
    if allowed("assets"):
        invested = float(sum(
            float(a.current_value or 0) for a in user.assets
            if a.asset_type in ("stocks", "mutual_funds", "gold", "crypto", "property")
        ))

    # ---- derived ratios ---------------------------------------------------
    surplus = None
    if monthly_income is not None and monthly_expenses is not None:
        surplus = monthly_income - monthly_expenses

    savings_rate = None
    if monthly_income and monthly_income > 0 and surplus is not None:
        savings_rate = surplus / monthly_income

    emi_to_income = None
    if monthly_income and monthly_income > 0 and monthly_emi is not None:
        emi_to_income = monthly_emi / monthly_income

    ef_months = ef_target_amount = ef_gap = None
    if liquid_savings is not None and monthly_expenses is not None:
        if monthly_expenses > 0:
            ef_months = liquid_savings / monthly_expenses
            ef_target_amount = monthly_expenses * EMERGENCY_FUND_TARGET_MONTHS
            ef_gap = max(0.0, ef_target_amount - liquid_savings)
        else:
            ef_months = EMERGENCY_FUND_TARGET_MONTHS if liquid_savings > 0 else 0.0
            ef_target_amount = 0.0
            ef_gap = 0.0

    # ---- budget adherence -------------------------------------------------
    budget_total = budget_overspend = budget_overspend_pct = None
    if allowed("expenses"):
        budgeted = (
            db.session.query(db.func.coalesce(db.func.sum(Budget.budgeted_amount), 0))
            .filter(
                Budget.user_id == user.id,
                Budget.month == today.month,
                Budget.year == today.year,
            )
            .scalar()
        )
        budget_total = float(budgeted or 0)
        if budget_total == 0 and allowed("profile") and user.profile:
            budget_total = float(user.profile.total_budget or 0)
        if budget_total > 0 and monthly_expenses is not None:
            budget_overspend = max(0.0, monthly_expenses - budget_total)
            budget_overspend_pct = budget_overspend / budget_total

    # ---- goals ------------------------------------------------------------
    goals = []
    if allowed("goals"):
        for g in user.goals:
            months_left = max(
                0,
                (g.target_date.year - today.year) * 12
                + (g.target_date.month - today.month),
            )
            target = float(g.target_amount or 0)
            goals.append({
                "name": g.name,
                "target_amount": target,
                "target_date": g.target_date,
                "priority": g.priority,
                "months_left": months_left,
                "monthly_required": target / months_left if months_left else target,
            })
        goals.sort(key=lambda x: (x["months_left"], -x["target_amount"]))

    # ---- health score (existing engine, untouched) ------------------------
    # The engine scores the *ledger*. With no expenses logged it reads zero
    # spending as infinite runway and returns ~90/100 — which would sit on the
    # dashboard contradicting a priority card that correctly says the emergency
    # fund is thin. So we withhold the score rather than show a flattering
    # number derived from absent data. The formula itself is untouched.
    health = None
    score_unavailable_reason = None
    if not ({"income", "expenses", "accounts"} <= granted):
        score_unavailable_reason = "consent"
    elif expenses_source != "logged":
        score_unavailable_reason = "no_expense_data"
    else:
        health = health_engine.compute_health_score(user, today=today)

    metrics = {
        "monthly_income": monthly_income,
        "income_source": income_source,
        "monthly_expenses": monthly_expenses,
        "expenses_source": expenses_source,
        "monthly_emi": monthly_emi,
        "monthly_surplus": surplus,
        "savings_rate": savings_rate,
        "emi_to_income": emi_to_income,
        "liquid_savings": liquid_savings,
        "emergency_fund_months": ef_months,
        "emergency_fund_target_months": EMERGENCY_FUND_TARGET_MONTHS,
        "emergency_fund_target_amount": ef_target_amount,
        "emergency_fund_gap": ef_gap,
        "invested": invested,
        "insurance_spend": insurance_spend,
        "budget_total": budget_total,
        "budget_overspend": budget_overspend,
        "budget_overspend_pct": budget_overspend_pct,
        "goals": goals,
    }

    risks = _assess_risks(metrics)
    return {
        "as_of": today,
        "metrics": metrics,
        "health": health,
        "health_score": health["total"] if health else None,
        "score_unavailable_reason": score_unavailable_reason,
        "critical_risks": risks["critical"],
        "moderate_risks": risks["moderate"],
        "zone": _zone(health["total"] if health else None, risks),
        "consent": {
            "purpose": HEALTH_PURPOSE,
            "granted": sorted(granted),
            "missing": sorted(missing),
            "degraded": bool(missing),
            "version": consent_service.consent_version(user.id, HEALTH_PURPOSE),
        },
    }


def _assess_risks(m: dict) -> dict:
    """Structural risks that override a merely-decent score."""
    critical, moderate = [], []

    if m["monthly_surplus"] is not None and m["monthly_surplus"] < 0:
        critical.append("NEGATIVE_CASH_FLOW")
    if m["emergency_fund_months"] is not None and m["emergency_fund_months"] < 0.5:
        critical.append("ZERO_EMERGENCY_BUFFER")
    if m["emi_to_income"] is not None and m["emi_to_income"] > EMI_SEVERE:
        critical.append("SEVERE_EMI_BURDEN")

    if m["emergency_fund_months"] is not None and 0.5 <= m["emergency_fund_months"] < 3:
        moderate.append("LOW_EMERGENCY_BUFFER")
    if m["emi_to_income"] is not None and EMI_STRETCHED < m["emi_to_income"] <= EMI_SEVERE:
        moderate.append("HIGH_EMI_BURDEN")
    if m["savings_rate"] is not None and 0 <= m["savings_rate"] < 0.10:
        moderate.append("VERY_LOW_SAVINGS_RATE")
    if m["budget_overspend_pct"] is not None and m["budget_overspend_pct"] > 0.10:
        moderate.append("BUDGET_OVERSPENDING")

    return {"critical": critical, "moderate": moderate}


def _zone(score: float | None, risks: dict) -> str:
    """GREEN / YELLOW / RED — never score alone (spec §8).

    Risk always outranks the score, so a zone is still meaningful when the
    score is withheld: we just can't award GREEN without one.
    """
    if risks["critical"]:
        return "RED"
    if score is None:
        return "YELLOW" if risks["moderate"] else "UNKNOWN"
    if score < 45:
        return "RED"
    if score >= 70 and not risks["moderate"]:
        return "GREEN"
    return "YELLOW"


ZONE_LABELS = {
    "GREEN": "On track",
    "YELLOW": "Needs attention",
    "RED": "Needs action now",
    "UNKNOWN": "Not enough data",
}
