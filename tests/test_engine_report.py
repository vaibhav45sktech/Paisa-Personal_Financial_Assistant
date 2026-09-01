"""Diagnostic: prints the engine's actual output for the demo scenarios.

Run with `-s` to read the numbers:
    pytest tests/test_engine_report.py -s
"""
from datetime import date

from app.extensions import db
from app.models import Account, Category, Expense, FinancialProfile, Income
from app.services import (
    financial_context_service, priority_engine, statement_service,
)

TODAY = date.today()


def _report(user, title):
    ctx = financial_context_service.build_context(user, today=TODAY)
    m, h = ctx["metrics"], ctx["health"]
    print(f"\n=== {title} ===")
    print(f"  income={m['monthly_income']} ({m['income_source']})  "
          f"expenses={m['monthly_expenses']} ({m['expenses_source']})")
    print(f"  surplus={m['monthly_surplus']}  ef_months={m['emergency_fund_months']}")
    print(f"  score={h['total'] if h else None}  zone={ctx['zone']}")
    if h:
        for k, c in h["components"].items():
            print(f"      {k:20} {c['score']:>6} / {c['max']}")
    for r in priority_engine.rank(ctx, limit=3):
        print(f"  #{r['priority']} {r['type']:26} {r['severity']:9} "
              f"impact={r['impact']:<5} action={r['estimated_monthly_action']}")
    return ctx


def test_report_profile_only_vs_full_ledger(make_user):
    user = make_user("student")
    statement_service.seed_default_categories(user)

    account = Account(
        user_id=user.id, account_name="Savings", account_type="bank",
        current_balance=18000,
    )
    db.session.add(account)
    profile = FinancialProfile(
        user_id=user.id, income_type="Student", monthly_gross_income=35000,
    )
    db.session.add(profile)
    db.session.commit()

    # Give the profile a budget so the fallback path has something to use.
    from app.models import BudgetItem
    for cat, amt in [("Rent", 8000), ("Grocery", 6000), ("EMI", 4000),
                     ("Transportation", 3000), ("Miscellaneous", 4000)]:
        db.session.add(BudgetItem(profile_id=profile.id, category=cat, amount=amt))
    db.session.commit()

    ctx_a = _report(user, "A) PROFILE + BUDGET ONLY (no ledger rows)")

    def cat_id(name):
        return Category.query.filter_by(user_id=user.id, name=name).first().id

    db.session.add(Income(
        user_id=user.id, account_id=account.id, source="Family",
        amount=35000, date=TODAY.replace(day=1),
    ))
    for name, amt in [("EMI", 4000), ("Rent", 8000), ("Grocery", 6000),
                      ("Transportation", 3000), ("Miscellaneous", 4000)]:
        db.session.add(Expense(
            user_id=user.id, account_id=account.id, category_id=cat_id(name),
            amount=amt, date=TODAY.replace(day=2), description=name,
        ))
    db.session.commit()

    ctx_b = _report(user, "B) WITH FULL LEDGER (spec demo scenario)")

    # Both paths must agree on the headline advice.
    assert priority_engine.next_best_action(ctx_a)["type"] == "EMERGENCY_FUND"
    assert priority_engine.next_best_action(ctx_b)["type"] == "EMERGENCY_FUND"

    # With no expenses logged, the health engine reads zero spending as
    # infinite runway and returns ~90/100. Showing that next to a HIGH-severity
    # emergency-fund warning would be a flat contradiction, so the score is
    # withheld until there is real spending to score.
    assert ctx_a["health"] is None
    assert ctx_a["score_unavailable_reason"] == "no_expense_data"
    assert ctx_a["zone"] == "YELLOW", "risk still classifies the zone without a score"

    # Once the ledger is populated the score appears and reflects reality.
    assert ctx_b["health"] is not None
    assert ctx_b["health"]["total"] < 70


def test_empty_account_is_never_scored_as_frugal(make_user):
    """A user with a balance but no logged spending must not be scored.

    The health engine reads zero expenses as infinite runway and awards near
    full marks — the exact trap this guard exists to close.
    """
    user = make_user("general")
    db.session.add(Account(
        user_id=user.id, account_name="Savings", account_type="bank",
        current_balance=50000,
    ))
    db.session.commit()

    ctx = financial_context_service.build_context(user, today=TODAY)

    assert ctx["metrics"]["expenses_source"] is None
    assert ctx["health"] is None
    assert ctx["score_unavailable_reason"] == "no_expense_data"


def test_impact_is_meaningful_without_a_score(make_user):
    """With the score withheld, impact falls back to the component maximum
    rather than the misleading 0 that a maxed-out phantom score produced."""
    user = make_user("student")
    statement_service.seed_default_categories(user)
    db.session.add(Account(
        user_id=user.id, account_name="Savings", account_type="bank",
        current_balance=18000,
    ))
    profile = FinancialProfile(
        user_id=user.id, income_type="Student", monthly_gross_income=35000,
    )
    db.session.add(profile)
    db.session.commit()

    from app.models import BudgetItem
    db.session.add(BudgetItem(profile_id=profile.id, category="Rent", amount=25000))
    db.session.commit()

    ctx = financial_context_service.build_context(user, today=TODAY)
    nba = priority_engine.next_best_action(ctx)

    assert nba["type"] == "EMERGENCY_FUND"
    assert nba["impact"] == 30, "should fall back to the full component weight"
