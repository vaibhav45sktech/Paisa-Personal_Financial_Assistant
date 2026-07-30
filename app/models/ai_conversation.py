"""AI Coach — session + message models."""
import uuid
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db


class AISession(db.Model):
    __tablename__ = "ai_sessions"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    session_title = db.Column(db.String(120), nullable=False, default="New chat")
    created_at = db.Column(db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    messages = db.relationship(
        "AIMessage", back_populates="session",
        cascade="all, delete-orphan", order_by="AIMessage.timestamp",
    )


class AIMessage(db.Model):
    __tablename__ = "ai_messages"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("ai_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    role = db.Column(db.String(15), nullable=False)  # 'user' | 'assistant'
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc), nullable=False)

    session = db.relationship("AISession", back_populates="messages")
