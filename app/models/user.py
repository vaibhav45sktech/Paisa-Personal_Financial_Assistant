"""User model."""
import uuid
from datetime import datetime, timezone

from flask_login import UserMixin
from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db, bcrypt


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = db.Column(db.String(30), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120), nullable=True)
    profile_picture = db.Column(db.String(255), nullable=True)
    last_login = db.Column(db.DateTime(timezone=True), nullable=True)
    failed_login_attempts = db.Column(db.Integer, nullable=False, default=0)
    is_locked = db.Column(db.Boolean, nullable=False, default=False)
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

    # Relationships
    profile = db.relationship(
        "FinancialProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    goals = db.relationship(
        "FinancialGoal",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="FinancialGoal.target_date",
    )
    accounts = db.relationship(
        "Account", back_populates="user",
        cascade="all, delete-orphan", order_by="Account.created_at",
    )
    assets = db.relationship(
        "Asset", back_populates="user",
        cascade="all, delete-orphan", order_by="Asset.created_at",
    )
    transactions = db.relationship(
        "Transaction", back_populates="user",
        cascade="all, delete-orphan",
    )
    statements = db.relationship(
        "BankStatement", back_populates="user",
        cascade="all, delete-orphan", order_by="BankStatement.upload_date.desc()",
    )

    # Flask-Login expects `get_id` to return a string
    def get_id(self) -> str:
        return str(self.id)

    def set_password(self, password: str) -> None:
        self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

    def check_password(self, password: str) -> bool:
        return bcrypt.check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:
        return f"<User {self.username}>"
