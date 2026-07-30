"""Financial profile & budget item models."""
import uuid
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db


class FinancialProfile(db.Model):
    __tablename__ = "financial_profiles"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    income_type = db.Column(db.String(30), nullable=False)
    monthly_gross_income = db.Column(db.Numeric(12, 2), nullable=False, default=0)
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

    user = db.relationship("User", back_populates="profile")
    budget_items = db.relationship(
        "BudgetItem",
        back_populates="profile",
        cascade="all, delete-orphan",
        lazy="joined",
    )

    @property
    def budget_map(self) -> dict[str, float]:
        return {item.category: float(item.amount) for item in self.budget_items}

    @property
    def total_budget(self) -> float:
        return float(sum(item.amount for item in self.budget_items))

    @property
    def estimated_savings(self) -> float:
        return float(self.monthly_gross_income) - self.total_budget

    def __repr__(self) -> str:
        return f"<FinancialProfile user_id={self.user_id}>"


class BudgetItem(db.Model):
    __tablename__ = "budget_items"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("financial_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)

    profile = db.relationship("FinancialProfile", back_populates="budget_items")

    __table_args__ = (
        db.UniqueConstraint("profile_id", "category", name="uq_profile_category"),
    )

    def __repr__(self) -> str:
        return f"<BudgetItem {self.category}={self.amount}>"
