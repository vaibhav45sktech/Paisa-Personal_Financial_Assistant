"""Priority engine — deterministic ranking tests.

These build a context dict directly rather than going through the database, so
each case pins one rule's behaviour precisely.
"""
import pytest

from app.services import priority_engine


def make_ctx(**metrics):
    """A neutral, healthy context; override only what a case cares about."""
    base = {
        "monthly_income": 50000.0,
        "income_source": "logged",
        "monthly_expenses": 30000.0,
        "expenses_source": "logged",
        "monthly_emi": 0.0,
        "monthly_surplus": 20000.0,
        "savings_rate": 0.40,
        "emi_to_income": 0.0,
        "liquid_savings": 180000.0,
        "emergency_fund_months": 6.0,
        "emergency_fund_target_months": 6.0,
        "emergency_fund_target_amount": 180000.0,
        "emergency_fund_gap": 0.0,
        "invested": 100000.0,
        "insurance_spend": 2000.0,
        "budget_total": 30000.0,
        "budget_overspend": 0.0,
        "budget_overspend_pct": 0.0,
        "goals": [],
    }
    base.update(metrics)
    return {
        "metrics": base,
        "health": None,
        "health_score": 75,
        "critical_risks": [],
        "moderate_risks": [],
        "zone": "GREEN",
        "consent": {"granted": [], "missing": [], "degraded": False, "version": 1},
    }


def types_of(ranked):
    return [r["type"] for r in ranked]


# --- Individual rules -------------------------------------------------------

def test_healthy_profile_raises_nothing_urgent():
    ranked = priority_engine.rank(make_ctx())
    assert "EMERGENCY_FUND" not in types_of(ranked)
    assert "NEGATIVE_CASH_FLOW" not in types_of(ranked)


def test_negative_cash_flow_outranks_everything():
    ctx = make_ctx(
        monthly_income=30000, monthly_expenses=35000, monthly_surplus=-5000,
        savings_rate=-0.17, emergency_fund_months=0.4,
        emergency_fund_gap=200000, liquid_savings=14000,
    )
    ranked = priority_engine.rank(ctx)

    assert ranked[0]["type"] == "NEGATIVE_CASH_FLOW"
    assert ranked[0]["severity"] == "CRITICAL"
    assert ranked[0]["estimated_monthly_action"] == 5000


def test_emergency_fund_flagged_when_thin():
    ctx = make_ctx(
        liquid_savings=18000, emergency_fund_months=0.72,
        emergency_fund_gap=132000, emergency_fund_target_amount=150000,
    )
    ranked = priority_engine.rank(ctx)
    ef = next(r for r in ranked if r["type"] == "EMERGENCY_FUND")

    assert ef["severity"] == "HIGH"
    assert "LOW_EMERGENCY_BUFFER" in ef["reason_codes"]
    assert ef["gap_amount"] == 132000


def test_emergency_fund_contribution_never_exceeds_surplus():
    """A 12-month plan must not recommend saving more than the user has spare."""
    ctx = make_ctx(
        monthly_surplus=2000, liquid_savings=0,
        emergency_fund_months=0.0, emergency_fund_gap=180000,
        emergency_fund_target_amount=180000,
    )
    ef = next(r for r in priority_engine.rank(ctx) if r["type"] == "EMERGENCY_FUND")

    assert ef["estimated_monthly_action"] <= 2000


def test_emergency_fund_leaves_room_in_the_budget():
    """Committing 100% of surplus to one goal is a plan people abandon."""
    ctx = make_ctx(
        monthly_surplus=10000, liquid_savings=18000,
        emergency_fund_months=0.72, emergency_fund_gap=132000,
        emergency_fund_target_amount=150000,
    )
    ef = next(r for r in priority_engine.rank(ctx) if r["type"] == "EMERGENCY_FUND")

    assert ef["estimated_monthly_action"] < 10000
    assert ef["estimated_monthly_action"] == pytest.approx(7000, abs=1)


def test_emi_burden_flagged_above_threshold():
    ctx = make_ctx(monthly_emi=20000, emi_to_income=0.40, monthly_surplus=10000)
    debt = next(r for r in priority_engine.rank(ctx) if r["type"] == "HIGH_INTEREST_DEBT")

    assert debt["severity"] == "HIGH"
    assert debt["estimated_monthly_action"] == pytest.approx(2000, abs=1)


def test_severe_emi_burden_is_critical():
    ctx = make_ctx(monthly_emi=30000, emi_to_income=0.60, monthly_surplus=5000)
    debt = next(r for r in priority_engine.rank(ctx) if r["type"] == "HIGH_INTEREST_DEBT")

    assert debt["severity"] == "CRITICAL"
    assert "SEVERE_DEBT_SERVICE" in debt["reason_codes"]


def test_comfortable_emi_is_not_flagged():
    ctx = make_ctx(monthly_emi=5000, emi_to_income=0.10)
    assert "HIGH_INTEREST_DEBT" not in types_of(priority_engine.rank(ctx))


def test_budget_overspending_flagged():
    ctx = make_ctx(
        monthly_expenses=36000, budget_total=30000,
        budget_overspend=6000, budget_overspend_pct=0.20, monthly_surplus=14000,
    )
    over = next(r for r in priority_engine.rank(ctx) if r["type"] == "BUDGET_OVERSPENDING")

    assert over["estimated_monthly_action"] == 6000


def test_low_savings_rate_flagged():
    ctx = make_ctx(monthly_surplus=2500, savings_rate=0.05)
    low = next(r for r in priority_engine.rank(ctx) if r["type"] == "LOW_SAVINGS")

    assert low["estimated_monthly_action"] == pytest.approx(7500, abs=1)


def test_goal_shortfall_flagged_when_goals_exceed_surplus():
    ctx = make_ctx(
        monthly_surplus=3000,
        goals=[{
            "name": "Laptop", "target_amount": 60000, "target_date": None,
            "priority": "High", "months_left": 6, "monthly_required": 10000.0,
        }],
    )
    goal = next(r for r in priority_engine.rank(ctx) if r["type"] == "GOAL_SHORTFALL")

    assert goal["estimated_monthly_action"] == 7000


def test_goal_within_surplus_is_not_flagged():
    ctx = make_ctx(
        monthly_surplus=20000,
        goals=[{
            "name": "Laptop", "target_amount": 60000, "target_date": None,
            "priority": "High", "months_left": 12, "monthly_required": 5000.0,
        }],
    )
    assert "GOAL_SHORTFALL" not in types_of(priority_engine.rank(ctx))


# --- The anti-debt guardrail ------------------------------------------------

def test_investing_is_never_suggested_before_the_buffer_is_funded():
    ctx = make_ctx(emergency_fund_months=2.0, emergency_fund_gap=100000, invested=0)
    assert "INVESTMENT_AFTER_STABILITY" not in types_of(priority_engine.rank(ctx))


def test_investing_is_suggested_once_stable():
    ctx = make_ctx(emergency_fund_months=7.0, emergency_fund_gap=0, invested=0)
    ranked = priority_engine.rank(ctx, limit=8)
    assert "INVESTMENT_AFTER_STABILITY" in types_of(ranked)


def test_investing_not_suggested_while_emi_is_stretched():
    ctx = make_ctx(
        emergency_fund_months=8.0, emergency_fund_gap=0,
        monthly_emi=20000, emi_to_income=0.40,
    )
    assert "INVESTMENT_AFTER_STABILITY" not in types_of(priority_engine.rank(ctx, limit=8))


# --- Ordering ---------------------------------------------------------------

def test_ranking_is_deterministic_across_runs():
    ctx = make_ctx(
        monthly_surplus=1000, savings_rate=0.03, emergency_fund_months=0.5,
        emergency_fund_gap=150000, monthly_emi=15000, emi_to_income=0.38,
        budget_overspend=4000, budget_overspend_pct=0.15,
    )
    first = types_of(priority_engine.rank(ctx, limit=8))
    for _ in range(5):
        assert types_of(priority_engine.rank(ctx, limit=8)) == first


def test_severity_dominates_impact_in_ordering():
    """A CRITICAL item outranks a HIGH one even with a smaller score impact."""
    ctx = make_ctx(
        monthly_income=30000, monthly_expenses=35000, monthly_surplus=-5000,
        savings_rate=-0.17,
        emergency_fund_months=0.2, emergency_fund_gap=200000,
        liquid_savings=7000,
    )
    ranked = priority_engine.rank(ctx, limit=8)

    severities = [r["severity"] for r in ranked]
    assert severities == sorted(
        severities, key=lambda s: priority_engine.SEVERITY_RANK[s]
    )


def test_rank_assigns_sequential_priority_numbers():
    ctx = make_ctx(
        monthly_surplus=1000, savings_rate=0.03,
        emergency_fund_months=0.5, emergency_fund_gap=150000,
    )
    ranked = priority_engine.rank(ctx, limit=3)
    assert [r["priority"] for r in ranked] == list(range(1, len(ranked) + 1))


def test_rank_respects_the_limit():
    ctx = make_ctx(
        monthly_surplus=500, savings_rate=0.01,
        emergency_fund_months=0.3, emergency_fund_gap=170000,
        monthly_emi=18000, emi_to_income=0.45,
        budget_overspend=5000, budget_overspend_pct=0.2,
    )
    assert len(priority_engine.rank(ctx, limit=3)) == 3


def test_next_best_action_matches_first_ranked():
    ctx = make_ctx(emergency_fund_months=0.5, emergency_fund_gap=150000)
    assert priority_engine.next_best_action(ctx)["type"] == priority_engine.rank(ctx)[0]["type"]


# --- Missing data must not crash the engine --------------------------------

def test_rules_skip_cleanly_when_metrics_are_unavailable():
    """Revoked consent yields None metrics; no rule may raise on that."""
    ctx = make_ctx(
        monthly_income=None, monthly_expenses=None, monthly_surplus=None,
        savings_rate=None, emi_to_income=None, monthly_emi=None,
        liquid_savings=None, emergency_fund_months=None,
        emergency_fund_gap=None, emergency_fund_target_amount=None,
        invested=None, insurance_spend=None, budget_total=None,
        budget_overspend=None, budget_overspend_pct=None,
    )
    assert priority_engine.rank(ctx) == []


def test_zero_income_does_not_divide_by_zero():
    ctx = make_ctx(
        monthly_income=0, monthly_expenses=0, monthly_surplus=0,
        savings_rate=None, emi_to_income=None,
    )
    priority_engine.rank(ctx)  # must not raise
