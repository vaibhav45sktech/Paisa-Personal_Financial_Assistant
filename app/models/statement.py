"""BankStatement model — file upload metadata + ingestion status."""
import uuid
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db

STATEMENT_STATUS = ("pending", "processed", "failed")


class BankStatement(db.Model):
    __tablename__ = "bank_statements"

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
    filename = db.Column(db.String(255), nullable=False)
    upload_date = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    status = db.Column(db.String(20), nullable=False, default="pending")
    total_records_extracted = db.Column(db.Integer, nullable=False, default=0)

    user = db.relationship("User", back_populates="statements")
    account = db.relationship("Account", back_populates="statements")
    transactions = db.relationship(
        "Transaction", back_populates="statement", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<BankStatement {self.filename} [{self.status}]>"
