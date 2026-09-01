"""Consent engine tests — the gate every financial engine sits behind.

Covers spec CASE 6: once transaction consent is revoked, transaction data must
not be usable for that purpose.
"""
import pytest

from app.models.consent import Consent
from app.services import consent_service


def test_defaults_seed_full_matrix(make_user):
    user = make_user()
    for purpose, categories in consent_service.PURPOSE_CATEGORIES.items():
        for category in categories:
            assert consent_service.has_consent(user.id, category, purpose), (
                f"{category}/{purpose} should be granted after onboarding"
            )


def test_ensure_defaults_is_idempotent(make_user, db):
    user = make_user()
    before = Consent.query.filter_by(user_id=user.id).count()
    consent_service.ensure_defaults(user.id)
    assert Consent.query.filter_by(user_id=user.id).count() == before


def test_ensure_defaults_does_not_resurrect_a_revoke(make_user):
    """A user's explicit revoke must survive later default-seeding."""
    user = make_user()
    consent_service.revoke(user.id, "transactions", "ai_assistant")

    consent_service.ensure_defaults(user.id)

    assert not consent_service.has_consent(user.id, "transactions", "ai_assistant")


# --- CASE 6: revocation actually takes effect -------------------------------

def test_revoking_transactions_blocks_that_category(make_user):
    user = make_user()
    assert consent_service.has_consent(user.id, "transactions", "ai_assistant")

    consent_service.revoke(user.id, "transactions", "ai_assistant")

    assert not consent_service.has_consent(user.id, "transactions", "ai_assistant")
    assert "transactions" not in consent_service.granted_categories(user.id, "ai_assistant")
    assert "transactions" in consent_service.missing_categories(user.id, "ai_assistant")


def test_revocation_is_scoped_to_one_purpose(make_user):
    """Revoking transactions for the AI must not disturb budgeting."""
    user = make_user()
    consent_service.revoke(user.id, "transactions", "ai_assistant")

    assert consent_service.has_consent(user.id, "transactions", "budgeting")


def test_revoke_then_grant_round_trip(make_user):
    user = make_user()
    consent_service.revoke(user.id, "income", "purchase_advisor")
    assert not consent_service.has_consent(user.id, "income", "purchase_advisor")

    consent_service.grant(user.id, "income", "purchase_advisor")
    assert consent_service.has_consent(user.id, "income", "purchase_advisor")


def test_version_increments_on_each_state_flip(make_user):
    user = make_user()
    row = Consent.query.filter_by(
        user_id=user.id, data_category="income", purpose="purchase_advisor",
    ).first()
    start = row.version

    consent_service.revoke(user.id, "income", "purchase_advisor")
    consent_service.grant(user.id, "income", "purchase_advisor")

    assert row.version == start + 2


def test_repeat_revoke_does_not_inflate_version(make_user):
    user = make_user()
    consent_service.revoke(user.id, "income", "purchase_advisor")
    row = Consent.query.filter_by(
        user_id=user.id, data_category="income", purpose="purchase_advisor",
    ).first()
    version_after_first = row.version

    consent_service.revoke(user.id, "income", "purchase_advisor")

    assert row.version == version_after_first


# --- Fail-closed behaviour --------------------------------------------------

def test_missing_row_is_treated_as_no_consent(make_user):
    user = make_user(with_consents=False)
    assert not consent_service.has_consent(user.id, "income", "purchase_advisor")


def test_unknown_category_or_purpose_is_refused(make_user):
    user = make_user()
    assert not consent_service.has_consent(user.id, "horoscope", "purchase_advisor")
    assert not consent_service.has_consent(user.id, "income", "astrology")


def test_category_outside_a_purpose_scope_is_refused(make_user):
    """budgeting never declares 'assets', so it can't be granted by any route."""
    user = make_user()
    assert "assets" not in consent_service.PURPOSE_CATEGORIES["budgeting"]
    assert not consent_service.grant(user.id, "assets", "budgeting")
    assert not consent_service.has_consent(user.id, "assets", "budgeting")


def test_set_purpose_toggles_every_category(make_user):
    user = make_user()
    consent_service.set_purpose(user.id, "purchase_advisor", False)
    assert consent_service.granted_categories(user.id, "purchase_advisor") == set()
    assert not consent_service.is_purpose_usable(user.id, "purchase_advisor")

    consent_service.set_purpose(user.id, "purchase_advisor", True)
    assert consent_service.granted_categories(user.id, "purchase_advisor") == set(
        consent_service.PURPOSE_CATEGORIES["purchase_advisor"]
    )


def test_consent_is_per_user(make_user):
    """One user's revoke must never affect another's."""
    alice, bob = make_user(), make_user()
    consent_service.revoke(alice.id, "income", "purchase_advisor")

    assert not consent_service.has_consent(alice.id, "income", "purchase_advisor")
    assert consent_service.has_consent(bob.id, "income", "purchase_advisor")


# --- Read models ------------------------------------------------------------

def test_summary_counts_reflect_revocation(make_user):
    user = make_user()
    assert consent_service.summary(user.id)["categories_not_shared"] == 0

    # 'transactions' is only used by budgeting + ai_assistant; drop both.
    consent_service.revoke(user.id, "transactions", "budgeting")
    consent_service.revoke(user.id, "transactions", "ai_assistant")

    assert consent_service.summary(user.id)["categories_not_shared"] == 1


def test_grant_count_moves_even_when_category_stays_in_use(make_user):
    """A single revoke must be visible somewhere, even if the category lives on.

    'transactions' is still used by budgeting after this revoke, so the
    category count is unchanged — the grant count is what has to move.
    """
    user = make_user()
    before = consent_service.summary(user.id)

    consent_service.revoke(user.id, "transactions", "ai_assistant")
    after = consent_service.summary(user.id)

    assert after["categories_shared"] == before["categories_shared"]
    assert after["grants_active"] == before["grants_active"] - 1


def test_summary_flags_a_fully_switched_off_purpose(make_user):
    user = make_user()
    assert consent_service.summary(user.id)["purposes_off_count"] == 0

    consent_service.set_purpose(user.id, "purchase_advisor", False)
    result = consent_service.summary(user.id)

    assert result["purposes_off"] == ["purchase_advisor"]
    assert result["purposes_off_count"] == 1


def test_consent_matrix_shape(make_user):
    user = make_user()
    matrix = consent_service.consent_matrix(user.id)

    assert {g["purpose"] for g in matrix} == set(consent_service.PURPOSE_CATEGORIES)
    assert all(g["fully_granted"] for g in matrix)


def test_consent_version_tracks_highest(make_user):
    user = make_user()
    assert consent_service.consent_version(user.id, "purchase_advisor") == 1

    consent_service.revoke(user.id, "income", "purchase_advisor")

    assert consent_service.consent_version(user.id, "purchase_advisor") == 2
