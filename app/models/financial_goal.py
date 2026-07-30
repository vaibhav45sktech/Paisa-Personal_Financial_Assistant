"""Financial goal model."""
import uuid
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db


class FinancialGoal(db.Model):
    __tablename__ = "financial_goals"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = db.Column(db.String(80), nullable=False)
    target_amount = db.Column(db.Numeric(12, 2), nullable=False)
    target_date = db.Column(db.Date, nullable=False)
    priority = db.Column(db.String(10), nullable=False, default="Medium")
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = db.relationship("User", back_populates="goals")

    @property
    def monthly_save_estimate(self) -> float:
        today = datetime.now(timezone.utc).date()
        months = max(
            0,
            (self.target_date.year - today.year) * 12
            + (self.target_date.month - today.month),
        )
        if months == 0:
            return float(self.target_amount)
        return float(self.target_amount) / months

    def __repr__(self) -> str:
        return f"<FinancialGoal {self.name}>"
