"""Deterministic ranking of what a user should fix first.

No LLM participates in this decision. Each rule is a pure function of the
metrics in `financial_context_service.build_context`; the ordering is a stable
sort over (severity, recoverable health-score impact, fixed tie-break).

`impact` is not invented — it is the number of points the existing health
engine is currently withholding for that component, so "fix this to recover
~18 points" is literally true against `health_engine.compute_health_score`.
"""
from __future__ import annotations

from app.services.financial_context_service import (
    EMERGENCY_FUND_TARGET_MONTHS, EMI_SEVERE, EMI_STRETCHED, HEALTHY_SAVINGS_RATE,
)

SEVERITY_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}

# Stable tie-break when severity and impact match. Lower sorts first — this
# encodes the spec's ordering: stabilise cash flow, then buffer, then debt,
# then discipline, then growth.
TYPE_ORDER = [
    "NEGATIVE_CASH_FLOW",
    "EMERGENCY_FUND",
    "HIGH_INTEREST_DEBT",
    "BUDGET_OVERSPENDING",
    "LOW_SAVINGS",
    "GOAL_SHORTFALL",
    "INSURANCE_GAP",
    "INVESTMENT_AFTER_STABILITY",
]

# Default horizon for closing an emergency-fund gap.
EF_HORIZON_MONTHS = 12
# Never ask a user to commit their whole surplus to one goal — they still need
# room for goals and ordinary life, or the plan gets abandoned in week two.
EF_MAX_SURPLUS_SHARE = 0.7


def _component_gap(ctx: dict, key: str, maximum: float) -> float:
    """Points the health engine is currently withholding for one component."""
    health = ctx.get("health")
    if not health:
        return maximum
    comp = health["components"].get(key)
    if not comp:
        return maximum
    return round(max(0.0, comp["max"] - comp["score"]), 1)


def _money(v: float) -> float:
    return round(float(v or 0), 2)


# --- Rules ------------------------------------------------------------------
# Each returns a candidate dict, or None when it doesn't apply / lacks data.

def _rule_negative_cash_flow(ctx: dict):
    m = ctx["metrics"]
    surplus = m["monthly_surplus"]
    if surplus is None or surplus >= 0:
        return None

    deficit = abs(surplus)
    return {
        "type": "NEGATIVE_CASH_FLOW",
        "severity": "CRITICAL",
        "title": "Close your monthly shortfall",
        "summary": "You're spending more than you earn each month.",
        "impact": _component_gap(ctx, "savings_rate", 20),
        "reason_codes": ["SPENDING_EXCEEDS_INCOME", "NO_MONTHLY_SURPLUS"],
        "estimated_monthly_action": _money(deficit),
        "action_label": "Reduce monthly outgoings by",
        "explanation_data": {
            "Monthly income": m["monthly_income"],
            "Monthly expenses": m["monthly_expenses"],
            "Monthly shortfall": deficit,
        },
        "reason": (
            f"Your expenses exceed your income by ₹{deficit:,.0f} a month. "
            "Every other goal is unreachable until this gap closes, because the "
            "shortfall has to be funded from savings or borrowing."
        ),
        "target": "A positive monthly surplus",
    }


def _rule_emergency_fund(ctx: dict):
    m = ctx["metrics"]
    months = m["emergency_fund_months"]
    if months is None or months >= EMERGENCY_FUND_TARGET_MONTHS:
        return None

    gap = m["emergency_fund_gap"] or 0
    if gap <= 0:
        return None

    surplus = m["monthly_surplus"]
    ideal = gap / EF_HORIZON_MONTHS
    # Never recommend saving more than the surplus realistically allows.
    if surplus is not None and surplus > 0:
        suggested = min(ideal, surplus * EF_MAX_SURPLUS_SHARE)
    else:
        suggested = ideal
    eta = int(round(gap / suggested)) if suggested > 0 else None

    if months < 1:
        severity, codes = "HIGH", ["LOW_EMERGENCY_BUFFER", "HIGH_EXPENSE_EXPOSURE"]
    elif months < 3:
        severity, codes = "HIGH", ["LOW_EMERGENCY_BUFFER"]
    else:
        severity, codes = "MEDIUM", ["PARTIAL_EMERGENCY_BUFFER"]

    return {
        "type": "EMERGENCY_FUND",
        "severity": severity,
        "title": "Build your emergency fund",
        "summary": f"Your buffer covers about {months:.1f} months of expenses.",
        "impact": _component_gap(ctx, "emergency_fund", 30),
        "reason_codes": codes,
        "estimated_monthly_action": _money(suggested),
        "action_label": "Set aside each month",
        "eta_months": eta,
        "current_amount": m["liquid_savings"],
        "target_amount": m["emergency_fund_target_amount"],
        "gap_amount": gap,
        "explanation_data": {
            "Liquid savings": m["liquid_savings"],
            "Monthly expenses": m["monthly_expenses"],
            "Cover at today's spending": f"{months:.1f} months",
            "Recommended cover": f"{EMERGENCY_FUND_TARGET_MONTHS:.0f} months",
            "Shortfall": gap,
        },
        "reason": (
            f"Your emergency fund currently covers approximately {months:.1f} months "
            f"of expenses, against a recommended {EMERGENCY_FUND_TARGET_MONTHS:.0f} months. "
            "Without that cushion, an unexpected cost turns into debt."
        ),
        "target": f"{EMERGENCY_FUND_TARGET_MONTHS:.0f} months of expenses saved",
    }


def _rule_high_interest_debt(ctx: dict):
    m = ctx["metrics"]
    ratio, emi, income = m["emi_to_income"], m["monthly_emi"], m["monthly_income"]
    if ratio is None or emi is None or not income or ratio <= EMI_STRETCHED:
        return None

    comfortable = income * EMI_STRETCHED
    excess = max(0.0, emi - comfortable)
    severity = "CRITICAL" if ratio > EMI_SEVERE else "HIGH"
    codes = ["HIGH_EMI_BURDEN"]
    if ratio > EMI_SEVERE:
        codes.append("SEVERE_DEBT_SERVICE")

    return {
        "type": "HIGH_INTEREST_DEBT",
        "severity": severity,
        "title": "Bring down your EMI burden",
        "summary": f"EMIs take {ratio * 100:.0f}% of your income.",
        "impact": _component_gap(ctx, "dti", 25),
        "reason_codes": codes,
        "estimated_monthly_action": _money(excess),
        "action_label": "Reduce monthly EMI by",
        "explanation_data": {
            "Monthly income": income,
            "Monthly EMI": emi,
            "EMI as share of income": f"{ratio * 100:.1f}%",
            "Comfortable ceiling": f"{EMI_STRETCHED * 100:.0f}% (₹{comfortable:,.0f})",
        },
        "reason": (
            f"EMI payments consume {ratio * 100:.0f}% of your monthly income, above the "
            f"{EMI_STRETCHED * 100:.0f}% level where repayments stay comfortable. "
            "Clearing the costliest balance first frees the most cash."
        ),
        "target": f"EMIs under {EMI_STRETCHED * 100:.0f}% of income",
    }


def _rule_budget_overspending(ctx: dict):
    m = ctx["metrics"]
    over, pct = m["budget_overspend"], m["budget_overspend_pct"]
    if over is None or pct is None or pct <= 0.10:
        return None

    return {
        "type": "BUDGET_OVERSPENDING",
        "severity": "MEDIUM",
        "title": "Rein in overspending",
        "summary": f"You're {pct * 100:.0f}% over budget this month.",
        "impact": _component_gap(ctx, "budget_discipline", 15),
        "reason_codes": ["BUDGET_EXCEEDED"],
        "estimated_monthly_action": _money(over),
        "action_label": "Trim spending by",
        "explanation_data": {
            "Budgeted this month": m["budget_total"],
            "Actually spent": m["monthly_expenses"],
            "Over by": over,
            "Overspend": f"{pct * 100:.1f}%",
        },
        "reason": (
            f"You've spent ₹{over:,.0f} more than you budgeted this month "
            f"({pct * 100:.0f}% over). Bringing spending back in line is usually the "
            "fastest way to free up cash without changing your income."
        ),
        "target": "Spending within budget",
    }


def _rule_low_savings(ctx: dict):
    m = ctx["metrics"]
    rate, income, surplus = m["savings_rate"], m["monthly_income"], m["monthly_surplus"]
    if rate is None or not income or surplus is None or surplus < 0:
        return None
    if rate >= HEALTHY_SAVINGS_RATE:
        return None

    target_amount = income * HEALTHY_SAVINGS_RATE
    gap = max(0.0, target_amount - surplus)
    return {
        "type": "LOW_SAVINGS",
        "severity": "MEDIUM",
        "title": "Raise your savings rate",
        "summary": f"You're saving {rate * 100:.0f}% of income.",
        "impact": _component_gap(ctx, "savings_rate", 20),
        "reason_codes": ["LOW_SAVINGS_RATE"],
        "estimated_monthly_action": _money(gap),
        "action_label": "Save an extra",
        "explanation_data": {
            "Monthly income": income,
            "Monthly surplus": surplus,
            "Savings rate": f"{rate * 100:.1f}%",
            "Healthy savings rate": f"{HEALTHY_SAVINGS_RATE * 100:.0f}% (₹{target_amount:,.0f})",
        },
        "reason": (
            f"You're saving about {rate * 100:.0f}% of your income, below the "
            f"{HEALTHY_SAVINGS_RATE * 100:.0f}% that keeps goals on track. "
            "A standing transfer on payday is the most reliable fix."
        ),
        "target": f"{HEALTHY_SAVINGS_RATE * 100:.0f}% of income saved",
    }


def _rule_goal_shortfall(ctx: dict):
    m = ctx["metrics"]
    goals, surplus = m["goals"], m["monthly_surplus"]
    if not goals or surplus is None:
        return None

    needed = sum(g["monthly_required"] for g in goals)
    if needed <= max(0.0, surplus):
        return None

    nearest = goals[0]
    shortfall = needed - max(0.0, surplus)
    return {
        "type": "GOAL_SHORTFALL",
        "severity": "MEDIUM" if surplus > 0 else "HIGH",
        "title": "Your goals need more than you're saving",
        "summary": f"Goals require ₹{needed:,.0f}/month; you have ₹{max(0.0, surplus):,.0f}.",
        "impact": round(min(10.0, shortfall / max(needed, 1) * 10), 1),
        "reason_codes": ["GOAL_FUNDING_SHORTFALL"],
        "estimated_monthly_action": _money(shortfall),
        "action_label": "Monthly gap to close",
        "explanation_data": {
            "Goals tracked": len(goals),
            "Required every month": needed,
            "Available surplus": max(0.0, surplus),
            "Monthly gap": shortfall,
            "Nearest goal": f"{nearest['name']} — ₹{nearest['target_amount']:,.0f} "
                            f"in {nearest['months_left']} months",
        },
        "reason": (
            f"Hitting every goal on time needs ₹{needed:,.0f} a month, but only "
            f"₹{max(0.0, surplus):,.0f} is spare. Either extend a deadline or lower a "
            "target — stretching further on the same income usually fails."
        ),
        "target": "Goal contributions within your surplus",
    }


def _rule_insurance_gap(ctx: dict):
    m = ctx["metrics"]
    spend, income = m["insurance_spend"], m["monthly_income"]
    if spend is None or not income or spend > 0:
        return None
    # Only worth raising once the basics are handled.
    if (m["emergency_fund_months"] or 0) < 1:
        return None

    return {
        "type": "INSURANCE_GAP",
        "severity": "LOW",
        "title": "No insurance cover recorded",
        "summary": "We can't see any insurance premium in your spending.",
        "impact": 0.0,
        "reason_codes": ["NO_INSURANCE_RECORDED"],
        "estimated_monthly_action": None,
        "action_label": None,
        "explanation_data": {
            "Insurance spend this month": 0,
            "Monthly income": income,
        },
        "reason": (
            "No insurance premium appears in this month's spending. If you do hold "
            "cover, log it so this check stays accurate; if not, health cover is "
            "usually the cheapest protection for your savings."
        ),
        "target": "Basic health cover in place",
    }


def _rule_investment_after_stability(ctx: dict):
    m = ctx["metrics"]
    months, surplus = m["emergency_fund_months"], m["monthly_surplus"]
    if months is None or surplus is None:
        return None
    # Deliberately gated: never suggest investing before the buffer and debt
    # are in order.
    if months < EMERGENCY_FUND_TARGET_MONTHS or surplus <= 0:
        return None
    if (m["emi_to_income"] or 0) > EMI_STRETCHED:
        return None

    suggested = surplus * 0.5
    return {
        "type": "INVESTMENT_AFTER_STABILITY",
        "severity": "LOW",
        "title": "Put your surplus to work",
        "summary": "Your buffer is funded — surplus can start compounding.",
        "impact": _component_gap(ctx, "investment_ratio", 10),
        "reason_codes": ["STABLE_BASE", "IDLE_SURPLUS"],
        "estimated_monthly_action": _money(suggested),
        "action_label": "Consider investing",
        "explanation_data": {
            "Emergency fund cover": f"{months:.1f} months",
            "Monthly surplus": surplus,
            "Currently invested": m["invested"],
        },
        "reason": (
            f"Your emergency fund covers {months:.1f} months and debt is under control, "
            "so idle surplus is now the main drag. This is the right stage to invest — "
            "not before."
        ),
        "target": "Surplus allocated rather than idle",
    }


RULES = (
    _rule_negative_cash_flow,
    _rule_emergency_fund,
    _rule_high_interest_debt,
    _rule_budget_overspending,
    _rule_low_savings,
    _rule_goal_shortfall,
    _rule_insurance_gap,
    _rule_investment_after_stability,
)


def rank(ctx: dict, *, limit: int = 3) -> list[dict]:
    """Return the top `limit` recommendations, highest priority first."""
    candidates = []
    for rule in RULES:
        found = rule(ctx)
        if found:
            candidates.append(found)

    candidates.sort(key=lambda c: (
        SEVERITY_RANK.get(c["severity"], 9),
        -c["impact"],
        TYPE_ORDER.index(c["type"]) if c["type"] in TYPE_ORDER else 99,
    ))

    for i, c in enumerate(candidates, start=1):
        c["priority"] = i
    return candidates[:limit]


def next_best_action(ctx: dict) -> dict | None:
    """The single highest-priority action, or None when nothing needs fixing."""
    ranked = rank(ctx, limit=1)
    return ranked[0] if ranked else None


ALL_CLEAR = {
    "type": "ALL_CLEAR",
    "severity": "LOW",
    "title": "Nothing urgent to fix",
    "summary": "Your buffer, cash flow and debt all look healthy.",
    "reason": (
        "No rule in the priority engine triggered: your emergency fund, cash flow, "
        "EMI burden, savings rate and goal funding are all within target."
    ),
}
