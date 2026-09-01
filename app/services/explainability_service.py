"""Turns a deterministic recommendation into an auditable explanation.

Structure per the spec: WHAT / WHY / DATA USED / IMPACT / WHAT TO DO.

Everything here is derived from the engine output — this module never decides
anything, it only presents. The natural-language phrasing may come from Gemini
(see `ai_service.phrase_recommendation`), but the numbers and the ranking never
do; if the model is unavailable the deterministic `reason` text is shown as-is.
"""
from __future__ import annotations

from app.services.financial_context_service import (
    DECISION_FACTORS, EXCLUDED_FACTORS,
)

SEVERITY_STYLES = {
    "CRITICAL": {"badge": "danger", "dot": "🔴", "label": "Critical"},
    "HIGH": {"badge": "danger", "dot": "🔴", "label": "High priority"},
    "MEDIUM": {"badge": "warning", "dot": "🟡", "label": "Worth fixing"},
    "LOW": {"badge": "success", "dot": "🟢", "label": "Nice to have"},
}

ZONE_STYLES = {
    "GREEN": {"badge": "success", "dot": "🟢"},
    "YELLOW": {"badge": "warning", "dot": "🟡"},
    "RED": {"badge": "danger", "dot": "🔴"},
    "UNKNOWN": {"badge": "secondary", "dot": "⚪"},
}

# Human-readable meaning for every code the engine can emit, so the UI never
# shows a bare constant.
REASON_CODE_LABELS = {
    "SPENDING_EXCEEDS_INCOME": "Spending exceeds income",
    "NO_MONTHLY_SURPLUS": "No monthly surplus",
    "LOW_EMERGENCY_BUFFER": "Emergency buffer below target",
    "PARTIAL_EMERGENCY_BUFFER": "Emergency buffer partly funded",
    "HIGH_EXPENSE_EXPOSURE": "High expense exposure",
    "HIGH_EMI_BURDEN": "EMI burden above comfortable level",
    "SEVERE_DEBT_SERVICE": "Debt service critically high",
    "BUDGET_EXCEEDED": "Budget exceeded this month",
    "LOW_SAVINGS_RATE": "Savings rate below target",
    "GOAL_FUNDING_SHORTFALL": "Goals underfunded",
    "NO_INSURANCE_RECORDED": "No insurance cover recorded",
    "STABLE_BASE": "Financial base is stable",
    "IDLE_SURPLUS": "Surplus sitting idle",
}


def _fmt(value) -> str:
    """Money gets INR formatting; everything else passes through."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"₹{value:,.0f}"
    return str(value)


def explain(recommendation: dict, ctx: dict, *, phrasing: str | None = None) -> dict:
    """Assemble the full explanation block for one recommendation."""
    style = SEVERITY_STYLES.get(recommendation["severity"], SEVERITY_STYLES["LOW"])

    what_to_do = []
    amount = recommendation.get("estimated_monthly_action")
    label = recommendation.get("action_label")
    if amount and label:
        what_to_do.append(f"{label} ₹{amount:,.0f} a month.")
    if recommendation.get("eta_months"):
        what_to_do.append(
            f"At that rate you'd reach the target in about "
            f"{recommendation['eta_months']} months."
        )
    if recommendation.get("target"):
        what_to_do.append(f"Target: {recommendation['target']}.")

    return {
        "what": recommendation["title"],
        "summary": recommendation.get("summary", ""),
        # Gemini's phrasing when available, the engine's own sentence otherwise.
        "why": phrasing or recommendation.get("reason", ""),
        "why_is_ai_phrased": bool(phrasing),
        "deterministic_reason": recommendation.get("reason", ""),
        "data_used": [
            {"label": k, "value": _fmt(v)}
            for k, v in (recommendation.get("explanation_data") or {}).items()
        ],
        "impact": recommendation.get("impact", 0),
        "impact_note": _impact_note(recommendation, ctx),
        "what_to_do": what_to_do,
        "reason_codes": [
            {"code": c, "label": REASON_CODE_LABELS.get(c, c.replace("_", " ").title())}
            for c in recommendation.get("reason_codes", [])
        ],
        "severity": recommendation["severity"],
        "severity_label": style["label"],
        "badge": style["badge"],
        "dot": style["dot"],
    }


def _impact_note(recommendation: dict, ctx: dict) -> str:
    impact = recommendation.get("impact") or 0
    if impact <= 0:
        return "This doesn't move your score directly, but it protects what you've built."
    score = ctx.get("health_score")
    if score is None:
        return f"Fixing this recovers about {impact:.0f} points of your health score."
    return (
        f"Fixing this recovers about {impact:.0f} points — taking your score from "
        f"{score:.0f} towards {min(100, score + impact):.0f}."
    )


def decision_factors(ctx: dict) -> dict:
    """What the engine was allowed to look at, and what it never looks at."""
    granted = set(ctx["consent"]["granted"])
    factors = [
        {
            "label": label,
            "category": category,
            "used": category in granted,
        }
        for label, category in DECISION_FACTORS
    ]
    return {
        "used": [f for f in factors if f["used"]],
        "withheld": [f for f in factors if not f["used"]],
        "never_used": EXCLUDED_FACTORS,
        "degraded": ctx["consent"]["degraded"],
        "consent_version": ctx["consent"]["version"],
    }


def score_breakdown(ctx: dict) -> list[dict]:
    """'Why is my score X?' — the health engine's components, made readable."""
    health = ctx.get("health")
    if not health:
        return []

    m = ctx["metrics"]
    readable = {
        "emergency_fund": (
            "Emergency fund",
            lambda c: f"Covers {c['months']:.1f} months of expenses "
                      f"(target {m['emergency_fund_target_months']:.0f}).",
        ),
        "savings_rate": (
            "Savings rate",
            lambda c: f"You're saving {c['rate_pct']:.0f}% of income.",
        ),
        "dti": (
            "Debt-to-income",
            lambda c: f"EMIs take {c['ratio_pct']:.0f}% of income.",
        ),
        "investment_ratio": (
            "Investments",
            lambda c: f"{c['ratio_pct']:.0f}% of your wealth is invested.",
        ),
        "budget_discipline": (
            "Budget discipline",
            lambda c: f"Spent ₹{c['monthly_expenses']:,.0f} against "
                      f"₹{c['total_budget']:,.0f} budgeted.",
        ),
    }

    rows = []
    for key, comp in health["components"].items():
        label, describe = readable.get(key, (key.replace("_", " ").title(), None))
        try:
            reason = describe(comp) if describe else ""
        except (KeyError, TypeError, ZeroDivisionError):
            reason = ""
        rows.append({
            "key": key,
            "label": label,
            "score": comp["score"],
            "max": comp["max"],
            "pct": (comp["score"] / comp["max"] * 100) if comp["max"] else 0,
            "reason": reason,
            "shortfall": round(comp["max"] - comp["score"], 1),
        })
    rows.sort(key=lambda r: -r["shortfall"])
    return rows
