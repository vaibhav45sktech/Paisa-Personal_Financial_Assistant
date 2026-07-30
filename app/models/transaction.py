"""Transaction model — raw ingestion engine.

Decouples statement ingestion from Expenses/Income.
Once a transaction is `confirmed`, an Expense or Income record is generated
(or linked) in `services.statements_service.confirm_transactions`.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db

TRANSACTION_TYPES = ("credit", "debit")
TRANSACTION_STATUS = ("unreviewed", "confirmed", "ignored")


class Transaction(db.Model):
    __tablename__ = "transactions"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    account_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    statement_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("bank_statements.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    category_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
    )

    date = db.Column(db.Date, nullable=False)
    description = db.Column(db.Text, nullable=False)
    merchant = db.Column(db.String(255), nullable=True)
    amount = db.Column(db.Numeric(14, 2), nullable=False)  # always positive
    transaction_type = db.Column(db.String(10), nullable=False)  # credit / debit

    is_expense = db.Column(db.Boolean, nullable=False, default=False)
    is_income = db.Column(db.Boolean, nullable=False, default=False)
    is_transfer = db.Column(db.Boolean, nullable=False, default=False)

    status = db.Column(db.String(15), nullable=False, default="unreviewed")
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = db.relationship("User", back_populates="transactions")
    account = db.relationship("Account", back_populates="transactions")
    statement = db.relationship("BankStatement", back_populates="transactions")
    category = db.relationship("Category")

    def __repr__(self) -> str:
        return f"<Txn {self.date} {self.transaction_type} {self.amount}>"
