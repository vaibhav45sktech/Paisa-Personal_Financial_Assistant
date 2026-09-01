"""Consent enforcement — the gate in front of every financial engine.

`has_consent` is the single check every engine calls before reading a data
category. A category with no row, or a revoked row, is treated as *not*
consented and the caller must degrade rather than read the data.

The purpose→category map below is the contract: it declares, per feature,
exactly which financial inputs that feature is allowed to touch. Nothing in
here references a protected characteristic — the engines score money, not
people.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.extensions import db
from app.models.consent import (
    Consent, DATA_CATEGORIES, PURPOSES, CONSENT_POLICY_VERSION,
)

# --- Which data each purpose is allowed to read -----------------------------
# Keep these minimal: a purpose should only list what it genuinely needs.
PURPOSE_CATEGORIES: dict[str, tuple[str, ...]] = {
    "financial_health_analysis": (
        "profile", "income", "expenses", "accounts", "assets", "goals", "liabilities",
    ),
    "budgeting": ("profile", "expenses", "transactions"),
    "purchase_advisor": (
        "profile", "income", "expenses", "accounts", "liabilities",
    ),
    "alternative_recommendations": (
        "profile", "income", "expenses", "accounts", "assets", "goals",
    ),
    "ai_assistant": (
        "profile", "income", "expenses", "goals", "transactions",
    ),
    "credit_readiness": (
        "profile", "income", "expenses", "accounts", "liabilities",
    ),
}

PURPOSE_LABELS = {
    "financial_health_analysis": "Financial Health Analysis",
    "budgeting": "Budgeting",
    "purchase_advisor": "Purchase Advisor",
    "alternative_recommendations": "Alternative Recommendations",
    "ai_assistant": "AI Assistant",
    "credit_readiness": "Credit Readiness",
}

PURPOSE_DESCRIPTIONS = {
    "financial_health_analysis": "Scores your financial health and works out your risk zone.",
    "budgeting": "Compares what you budgeted against what you actually spent.",
    "purchase_advisor": "Stress-tests a purchase against your cash flow before you commit.",
    "alternative_recommendations": "Finds non-credit options before any borrowing is suggested.",
    "ai_assistant": "Lets the AI coach explain your numbers in plain language.",
    "credit_readiness": "Assesses whether borrowing would be safe for you right now.",
}

CATEGORY_LABELS = {
    "profile": "Financial profile",
    "income": "Income",
    "expenses": "Expenses",
    "transactions": "Transactions",
    "bank_statement": "Bank statements",
    "accounts": "Accounts & savings",
    "assets": "Assets",
    "liabilities": "Liabilities & EMI",
    "goals": "Goals",
    "insurance": "Insurance",
    "investments": "Investments",
}


def _now():
    return datetime.now(timezone.utc)


# --- Core check -------------------------------------------------------------

def has_consent(user_id, data_category: str, purpose: str) -> bool:
    """True only when an explicit, un-revoked grant exists.

    Absent row == no consent. Callers must handle False by omitting that input,
    never by falling back to reading it anyway.
    """
    if data_category not in DATA_CATEGORIES or purpose not in PURPOSES:
        return False
    # A category the purpose never declared is out of scope regardless of rows.
    if data_category not in PURPOSE_CATEGORIES.get(purpose, ()):
        return False

    row = Consent.query.filter_by(
        user_id=user_id, data_category=data_category, purpose=purpose,
    ).first()
    return bool(row and row.granted)


def granted_categories(user_id, purpose: str) -> set[str]:
    """Every category this user currently allows for `purpose`."""
    if purpose not in PURPOSES:
        return set()
    rows = Consent.query.filter_by(user_id=user_id, purpose=purpose, granted=True).all()
    allowed = set(PURPOSE_CATEGORIES.get(purpose, ()))
    return {r.data_category for r in rows if r.data_category in allowed}


def missing_categories(user_id, purpose: str) -> set[str]:
    """Categories the purpose needs but the user has not granted."""
    return set(PURPOSE_CATEGORIES.get(purpose, ())) - granted_categories(user_id, purpose)


def is_purpose_usable(user_id, purpose: str) -> bool:
    """A feature is usable when at least its profile+income basics are granted.

    Features degrade rather than hard-fail, so this is advisory: engines still
    check each category individually.
    """
    return bool(granted_categories(user_id, purpose))


def consent_version(user_id, purpose: str) -> int:
    """Highest version across the purpose's rows — recorded on audit entries."""
    rows = Consent.query.filter_by(user_id=user_id, purpose=purpose).all()
    return max((r.version for r in rows), default=0)


# --- Mutation ---------------------------------------------------------------

def _upsert(user_id, data_category: str, purpose: str, granted: bool, source: str) -> Consent | None:
    if data_category not in PURPOSE_CATEGORIES.get(purpose, ()):
        return None

    row = Consent.query.filter_by(
        user_id=user_id, data_category=data_category, purpose=purpose,
    ).first()

    if row is None:
        row = Consent(
            user_id=user_id,
            data_category=data_category,
            purpose=purpose,
            granted=granted,
            source=source,
            version=1,
            granted_at=_now() if granted else None,
            revoked_at=None if granted else _now(),
        )
        db.session.add(row)
        return row

    if row.granted != granted:
        row.version = (row.version or 1) + 1
        row.granted = granted
        row.source = source
        if granted:
            row.granted_at = _now()
            row.revoked_at = None
        else:
            row.revoked_at = _now()
    return row


def grant(user_id, data_category: str, purpose: str, *, source: str = "consent_center") -> bool:
    row = _upsert(user_id, data_category, purpose, True, source)
    if row is None:
        return False
    db.session.commit()
    return True


def revoke(user_id, data_category: str, purpose: str, *, source: str = "consent_center") -> bool:
    row = _upsert(user_id, data_category, purpose, False, source)
    if row is None:
        return False
    db.session.commit()
    return True


def set_purpose(user_id, purpose: str, granted: bool, *, source: str = "consent_center") -> bool:
    """Grant or revoke every category belonging to one purpose."""
    if purpose not in PURPOSES:
        return False
    for category in PURPOSE_CATEGORIES[purpose]:
        _upsert(user_id, category, purpose, granted, source)
    db.session.commit()
    return True


def ensure_defaults(user_id, *, source: str = "default_seed", granted: bool = True) -> None:
    """Seed a full consent matrix so existing features keep working post-signup.

    Only fills gaps — an explicit revoke by the user is never re-granted here.
    """
    existing = {
        (r.data_category, r.purpose)
        for r in Consent.query.filter_by(user_id=user_id).all()
    }
    created = False
    for purpose, categories in PURPOSE_CATEGORIES.items():
        for category in categories:
            if (category, purpose) in existing:
                continue
            db.session.add(Consent(
                user_id=user_id,
                data_category=category,
                purpose=purpose,
                granted=granted,
                source=source,
                version=1,
                granted_at=_now() if granted else None,
                revoked_at=None if granted else _now(),
            ))
            created = True
    if created:
        db.session.commit()


# --- Read model for the Consent Center UI -----------------------------------

def consent_matrix(user_id) -> list[dict]:
    """Purpose-grouped view of every consent decision, for rendering."""
    rows = Consent.query.filter_by(user_id=user_id).all()
    by_key = {(r.purpose, r.data_category): r for r in rows}

    matrix = []
    for purpose in PURPOSES:
        categories = []
        for category in PURPOSE_CATEGORIES[purpose]:
            row = by_key.get((purpose, category))
            categories.append({
                "category": category,
                "label": CATEGORY_LABELS.get(category, category.title()),
                "granted": bool(row and row.granted),
                "granted_at": row.granted_at if row else None,
                "revoked_at": row.revoked_at if row else None,
                "version": row.version if row else 0,
                "source": row.source if row else None,
            })
        granted_count = sum(1 for c in categories if c["granted"])
        matrix.append({
            "purpose": purpose,
            "label": PURPOSE_LABELS[purpose],
            "description": PURPOSE_DESCRIPTIONS[purpose],
            "categories": categories,
            "granted_count": granted_count,
            "total_count": len(categories),
            "fully_granted": granted_count == len(categories),
            "fully_revoked": granted_count == 0,
        })
    return matrix


def summary(user_id) -> dict:
    """Counts for the Consent Center header and the dashboard status card.

    Two different granularities, because they answer different questions:
      * categories  — "which kinds of my data are in use anywhere?"
      * grants      — "how many individual feature-to-data permissions are on?"
    Revoking one purpose often leaves a category still used elsewhere, so only
    the grant counts move. Showing both keeps the number honest.
    """
    rows = Consent.query.filter_by(user_id=user_id).all()
    granted_pairs = {
        (r.data_category, r.purpose) for r in rows
        if r.granted and r.data_category in PURPOSE_CATEGORIES.get(r.purpose, ())
    }
    shared = {category for category, _ in granted_pairs}
    all_used = {c for cats in PURPOSE_CATEGORIES.values() for c in cats}
    all_pairs = {
        (c, p) for p, cats in PURPOSE_CATEGORIES.items() for c in cats
    }
    revoked_purposes = [
        p for p in PURPOSES
        if not any(purpose == p for _, purpose in granted_pairs)
    ]
    return {
        "categories_shared": len(shared),
        "categories_not_shared": len(all_used - shared),
        "total_categories": len(all_used),
        "grants_active": len(granted_pairs),
        "grants_total": len(all_pairs),
        "purposes_off": revoked_purposes,
        "purposes_off_count": len(revoked_purposes),
        "policy_version": CONSENT_POLICY_VERSION,
    }
