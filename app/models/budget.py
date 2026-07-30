"""Budget model — per-category monthly budget."""
import uuid
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db


class Budget(db.Model):
    __tablename__ = "budgets"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    category_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    budgeted_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    month = db.Column(db.Integer, nullable=False)  # 1-12
    year = db.Column(db.Integer, nullable=False)

    __table_args__ = (
        db.UniqueConstraint(
            "user_id", "category_id", "month", "year",
            name="uq_budget_user_cat_period",
        ),
    )

    category = db.relationship("Category")

    def __repr__(self) -> str:
        return f"<Budget {self.month}/{self.year} cat={self.category_id}>"
