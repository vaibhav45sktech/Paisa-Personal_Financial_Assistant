"""Purchase model — impact analyzer inputs.

Per spec: stores INPUTS only. EMI, affordability, recommendations
are computed dynamically by `services.analyzer_service`.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db


class Purchase(db.Model):
    __tablename__ = "purchases"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    product_name = db.Column(db.String(120), nullable=False)
    product_price = db.Column(db.Numeric(14, 2), nullable=False)
    down_payment = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    loan_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    tenure_months = db.Column(db.Integer, nullable=False, default=0)
    interest_rate = db.Column(db.Numeric(5, 2), nullable=False, default=0)  # annual %
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc), nullable=False,
    )
