"""Consent model — records what financial data a user allows, per purpose.

Consent is the gate in front of every deterministic financial engine. A missing
or revoked row means the corresponding data category must not be read for that
purpose (see `services.consent_service`).
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db

# Bumped when the wording/scope of the consent policy itself changes. Stored on
# audit records so a past decision can be traced to the policy it ran under.
CONSENT_POLICY_VERSION = 1

# What kinds of data the engines can read.
DATA_CATEGORIES = (
    "profile",
    "income",
    "expenses",
    "transactions",
    "bank_statement",
    "accounts",
    "assets",
    "liabilities",
    "goals",
    "insurance",
    "investments",
)

# Why the data is read. One feature == one purpose.
PURPOSES = (
    "financial_health_analysis",
    "budgeting",
    "purchase_advisor",
    "alternative_recommendations",
    "ai_assistant",
    "credit_readiness",
)

CONSENT_SOURCES = ("onboarding", "consent_center", "default_seed")


class Consent(db.Model):
    __tablename__ = "consents"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    data_category = db.Column(db.String(30), nullable=False)
    purpose = db.Column(db.String(40), nullable=False)

    granted = db.Column(db.Boolean, nullable=False, default=False)
    granted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    revoked_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Incremented on every state flip, so an audit row can pin the exact grant.
    version = db.Column(db.Integer, nullable=False, default=1)
    source = db.Column(db.String(20), nullable=False, default="default_seed")

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = db.relationship("User", back_populates="consents")

    __table_args__ = (
        db.UniqueConstraint(
            "user_id", "data_category", "purpose", name="uq_consent_user_cat_purpose",
        ),
        db.Index("ix_consents_user_purpose", "user_id", "purpose"),
    )

    def __repr__(self) -> str:
        state = "granted" if self.granted else "revoked"
        return f"<Consent {self.data_category}/{self.purpose} {state}>"
