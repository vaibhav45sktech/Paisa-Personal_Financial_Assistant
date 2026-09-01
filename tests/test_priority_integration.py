"""End-to-end: real database rows -> context -> ranking.

Includes the spec's demo scenario (§26). The expected score is asserted as a
range derived from the engine, never hard-coded to a magic number.
"""
from datetime import date

import pytest

from app.extensions import db
from app.models import (
    Account, Category, Expense, Income, FinancialGoal, FinancialProfile,
)
from app.services import (
    financial_context_service, priority_engine, explainability_service,
    consent_service, statement_service,
)

TODAY = date.today()


def _category(user, name):
    return Category.query.filter_by(user_id=user.id, name=name).first()


@pytest.fixture
def demo_student(make_user):
    """Spec §26: income 35k, expenses 25k (incl. 4k EMI), savings 18k, laptop goal."""
    user = make_user("student")
    statement_service.seed_default_categories(user)

    account = Account(
        user_id=user.id, account_name="Savings", account_type="bank",
        current_balance=18000,
    )
    db.session.add(account)
    db.session.add(FinancialProfile(
        user_id=user.id, income_type="Student", monthly_gross_income=35000,
    ))
    db.session.commit()

    db.session.add(Income(
        user_id=user.id, account_id=account.id, source="Family support",
        amount=35000, date=TODAY.replace(day=1),
    ))
    for cat_name, amount in [
        ("EMI", 4000), ("Rent", 8000), ("Grocery", 6000),
        ("Transportation", 3000), ("Miscellaneous", 4000),
    ]:
        db.session.add(Expense(
            user_id=user.id, account_id=account.id,
            category_id=_category(user, cat_name).id,
            amount=amount, date=TODAY.replace(day=2), description=cat_name,
        ))
    db.session.add(FinancialGoal(
        user_id=user.id, name="Laptop", target_amount=60000,
        target_date=date(TODAY.year + 1, TODAY.month, 1), priority="High",
    ))
    db.session.commit()
    return user


# --- Demo scenario ----------------------------------------------------------

def test_demo_student_metrics_are_correct(demo_student):
    ctx = financial_context_service.build_context(demo_student, today=TODAY)
    m = ctx["metrics"]

    assert m["monthly_income"] == 35000
    assert m["monthly_expenses"] == 25000
    assert m["monthly_emi"] == 4000
    assert m["monthly_surplus"] == 10000
    assert m["liquid_savings"] == 18000
    assert m["emergency_fund_months"] == pytest.approx(0.72, abs=0.01)
    assert m["emi_to_income"] == pytest.approx(0.114, abs=0.01)
    assert m["savings_rate"] == pytest.approx(0.286, abs=0.01)


def test_demo_student_lands_in_yellow_zone(demo_student):
    ctx = financial_context_service.build_context(demo_student, today=TODAY)

    assert ctx["zone"] == "YELLOW"
    assert "LOW_EMERGENCY_BUFFER" in ctx["moderate_risks"]
    assert ctx["critical_risks"] == []


def test_demo_student_score_emerges_from_the_engine(demo_student):
    """Not hard-coded: assert the score is consistent with its own components."""
    ctx = financial_context_service.build_context(demo_student, today=TODAY)
    health = ctx["health"]

    component_total = sum(c["score"] for c in health["components"].values())
    assert health["total"] == pytest.approx(component_total, abs=0.2)
    assert 45 <= health["total"] < 70, "a YELLOW-zone score is expected here"


def test_demo_student_top_priority_is_the_emergency_fund(demo_student):
    ctx = financial_context_service.build_context(demo_student, today=TODAY)
    nba = priority_engine.next_best_action(ctx)

    assert nba["type"] == "EMERGENCY_FUND"
    assert nba["priority"] == 1
    assert nba["severity"] == "HIGH"
    assert nba["gap_amount"] == pytest.approx(132000, abs=1)


def test_demo_student_is_not_told_to_borrow_or_invest(demo_student):
    """The whole point: stabilise before growth, and never suggest debt."""
    ctx = financial_context_service.build_context(demo_student, today=TODAY)
    ranked = priority_engine.rank(ctx, limit=8)
    types = [r["type"] for r in ranked]

    assert "INVESTMENT_AFTER_STABILITY" not in types
    blob = " ".join(r["reason"] for r in ranked).lower()
    for word in ("loan", "borrow", "credit card", "emi offer"):
        assert word not in blob


def test_demo_student_goal_is_affordable_so_not_flagged(demo_student):
    """₹60k over 12 months = ₹5k/mo, inside a ₹10k surplus."""
    ctx = financial_context_service.build_context(demo_student, today=TODAY)
    types = [r["type"] for r in priority_engine.rank(ctx, limit=8)]

    assert "GOAL_SHORTFALL" not in types


def test_explanation_carries_the_real_numbers(demo_student):
    ctx = financial_context_service.build_context(demo_student, today=TODAY)
    nba = priority_engine.next_best_action(ctx)
    detail = explainability_service.explain(nba, ctx)

    values = {row["label"]: row["value"] for row in detail["data_used"]}
    assert values["Liquid savings"] == "₹18,000"
    assert values["Monthly expenses"] == "₹25,000"
    assert detail["why"] == nba["reason"]          # no AI key -> engine wording
    assert detail["why_is_ai_phrased"] is False


# --- Consent actually gates the engine -------------------------------------

def test_revoking_accounts_removes_the_emergency_fund_rule(demo_student):
    """CASE 6 applied to the priority engine: revoked data can't drive advice."""
    consent_service.revoke(
        demo_student.id, "accounts", financial_context_service.HEALTH_PURPOSE,
    )
    ctx = financial_context_service.build_context(demo_student, today=TODAY)

    assert ctx["metrics"]["liquid_savings"] is None
    assert ctx["metrics"]["emergency_fund_months"] is None
    assert "EMERGENCY_FUND" not in [r["type"] for r in priority_engine.rank(ctx, limit=8)]
    assert ctx["consent"]["degraded"] is True


def test_revoking_income_stops_ratio_based_rules(demo_student):
    consent_service.revoke(
        demo_student.id, "income", financial_context_service.HEALTH_PURPOSE,
    )
    ctx = financial_context_service.build_context(demo_student, today=TODAY)

    assert ctx["metrics"]["monthly_income"] is None
    assert ctx["metrics"]["emi_to_income"] is None
    assert ctx["metrics"]["savings_rate"] is None


def test_decision_factors_report_withheld_data(demo_student):
    consent_service.revoke(
        demo_student.id, "goals", financial_context_service.HEALTH_PURPOSE,
    )
    ctx = financial_context_service.build_context(demo_student, today=TODAY)
    factors = explainability_service.decision_factors(ctx)

    withheld = [f["label"] for f in factors["withheld"]]
    assert "Savings goals" in withheld
    assert factors["degraded"] is True
    assert "Caste" in factors["never_used"]
    assert "Religion" in factors["never_used"]


# --- A genuinely healthy user ----------------------------------------------

def test_stable_user_gets_growth_advice_not_alarms(make_user):
    user = make_user("general")
    statement_service.seed_default_categories(user)
    account = Account(
        user_id=user.id, account_name="Savings", account_type="bank",
        current_balance=400000,
    )
    db.session.add(account)
    db.session.add(FinancialProfile(
        user_id=user.id, income_type="Monthly Salary", monthly_gross_income=100000,
    ))
    db.session.commit()

    db.session.add(Income(
        user_id=user.id, account_id=account.id, source="Salary",
        amount=100000, date=TODAY.replace(day=1),
    ))
    db.session.add(Expense(
        user_id=user.id, account_id=account.id,
        category_id=_category(user, "Rent").id,
        amount=40000, date=TODAY.replace(day=2), description="Rent",
    ))
    db.session.commit()

    ctx = financial_context_service.build_context(user, today=TODAY)
    types = [r["type"] for r in priority_engine.rank(ctx, limit=8)]

    assert ctx["metrics"]["emergency_fund_months"] == pytest.approx(10.0, abs=0.1)
    assert "EMERGENCY_FUND" not in types
    assert "NEGATIVE_CASH_FLOW" not in types
    assert ctx["zone"] == "GREEN"


def test_overspending_user_is_flagged_red(make_user):
    user = make_user("general")
    statement_service.seed_default_categories(user)
    account = Account(
        user_id=user.id, account_name="Savings", account_type="bank",
        current_balance=2000,
    )
    db.session.add(account)
    db.session.commit()

    db.session.add(Income(
        user_id=user.id, account_id=account.id, source="Salary",
        amount=20000, date=TODAY.replace(day=1),
    ))
    db.session.add(Expense(
        user_id=user.id, account_id=account.id,
        category_id=_category(user, "Rent").id,
        amount=26000, date=TODAY.replace(day=2), description="Rent",
    ))
    db.session.commit()

    ctx = financial_context_service.build_context(user, today=TODAY)
    ranked = priority_engine.rank(ctx, limit=8)

    assert ctx["metrics"]["monthly_surplus"] == -6000
    assert "NEGATIVE_CASH_FLOW" in ctx["critical_risks"]
    assert ctx["zone"] == "RED"
    assert ranked[0]["type"] == "NEGATIVE_CASH_FLOW"
