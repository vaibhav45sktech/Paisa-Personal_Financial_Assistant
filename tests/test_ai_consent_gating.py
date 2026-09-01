"""The AI context must honour consent — revoked data must never reach Gemini.

These tests build the prompt context directly, so they run without an API key
and without making any network call.
"""
from app.services import ai_service, consent_service


def test_context_includes_profile_when_consented(make_user, db):
    from app.models import FinancialProfile
    user = make_user()
    db.session.add(FinancialProfile(
        user_id=user.id, income_type="Student", monthly_gross_income=35000,
    ))
    db.session.commit()

    context = ai_service.build_financial_context(user)

    assert "Income type: Student" in context
    assert "35,000" in context


def test_revoking_profile_keeps_it_out_of_the_prompt(make_user, db):
    from app.models import FinancialProfile
    user = make_user()
    db.session.add(FinancialProfile(
        user_id=user.id, income_type="Student", monthly_gross_income=35000,
    ))
    db.session.commit()

    consent_service.revoke(user.id, "profile", ai_service.AI_PURPOSE)
    context = ai_service.build_financial_context(user)

    assert "Income type" not in context
    assert "35,000" not in context


def test_revoking_goals_keeps_them_out_of_the_prompt(make_user, db):
    from datetime import date
    from app.models import FinancialGoal
    user = make_user()
    db.session.add(FinancialGoal(
        user_id=user.id, name="Laptop", target_amount=60000,
        target_date=date(2027, 1, 1), priority="High",
    ))
    db.session.commit()

    assert "Laptop" in ai_service.build_financial_context(user)

    consent_service.revoke(user.id, "goals", ai_service.AI_PURPOSE)

    assert "Laptop" not in ai_service.build_financial_context(user)


def test_withheld_categories_are_declared_to_the_model(make_user):
    user = make_user()
    consent_service.revoke(user.id, "goals", ai_service.AI_PURPOSE)

    context = ai_service.build_financial_context(user)

    assert "has not shared" in context
    assert "goals" in context.lower()


def test_full_revocation_leaves_no_financial_figures(make_user, db):
    from app.models import FinancialProfile
    user = make_user()
    db.session.add(FinancialProfile(
        user_id=user.id, income_type="Student", monthly_gross_income=35000,
    ))
    db.session.commit()

    consent_service.set_purpose(user.id, ai_service.AI_PURPOSE, False)
    context = ai_service.build_financial_context(user)

    assert "35,000" not in context
    assert "Financial Health Score" not in context
    assert "Net Worth" not in context
    assert "has not shared" in context


def test_revoking_one_purpose_does_not_starve_the_ai(make_user, db):
    """Turning off the Purchase Advisor must not affect the coach's context."""
    from app.models import FinancialProfile
    user = make_user()
    db.session.add(FinancialProfile(
        user_id=user.id, income_type="Student", monthly_gross_income=35000,
    ))
    db.session.commit()

    consent_service.set_purpose(user.id, "purchase_advisor", False)
    context = ai_service.build_financial_context(user)

    assert "Income type: Student" in context
