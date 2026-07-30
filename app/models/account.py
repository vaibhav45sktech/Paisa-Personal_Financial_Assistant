"""Account model — bank/wallet/cash/credit_card/upi."""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db

ACCOUNT_TYPES = ("bank", "wallet", "cash", "credit_card", "upi")


class Account(db.Model):
    __tablename__ = "accounts"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    account_name = db.Column(db.String(80), nullable=False)
    account_type = db.Column(db.String(20), nullable=False, default="bank")
    current_balance = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = db.relationship("User", back_populates="accounts")
    transactions = db.relationship(
        "Transaction", back_populates="account", cascade="all, delete-orphan"
    )
    statements = db.relationship(
        "BankStatement", back_populates="account", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Account {self.account_name} ({self.account_type})>"
