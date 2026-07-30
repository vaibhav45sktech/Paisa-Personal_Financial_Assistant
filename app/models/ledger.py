"""Expenses & Income records generated from confirmed Transactions or manual entry."""
import uuid
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db


class Expense(db.Model):
    __tablename__ = "expenses"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True),
                        db.ForeignKey("users.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    account_id = db.Column(UUID(as_uuid=True),
                           db.ForeignKey("accounts.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    transaction_id = db.Column(UUID(as_uuid=True),
                               db.ForeignKey("transactions.id", ondelete="SET NULL"),
                               nullable=True, index=True)
    category_id = db.Column(UUID(as_uuid=True),
                            db.ForeignKey("categories.id", ondelete="SET NULL"),
                            nullable=True)
    description = db.Column(db.String(255), nullable=True)
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    date = db.Column(db.Date, nullable=False)
    recurring = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc), nullable=False,
    )

    category = db.relationship("Category")

    def __repr__(self) -> str:
        return f"<Expense {self.date} {self.amount}>"


class Income(db.Model):
    __tablename__ = "income"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True),
                        db.ForeignKey("users.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    account_id = db.Column(UUID(as_uuid=True),
                           db.ForeignKey("accounts.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    transaction_id = db.Column(UUID(as_uuid=True),
                               db.ForeignKey("transactions.id", ondelete="SET NULL"),
                               nullable=True, index=True)
    source = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    date = db.Column(db.Date, nullable=False)
    recurring = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc), nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Income {self.date} {self.amount}>"
