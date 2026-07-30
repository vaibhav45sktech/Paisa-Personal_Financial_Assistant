"""Notification model."""
import uuid
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db

NOTIFICATION_TYPES = ("alert", "info", "warning")
NOTIFICATION_PRIORITIES = ("low", "medium", "high")


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    title = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(15), nullable=False, default="info")
    priority = db.Column(db.String(10), nullable=False, default="medium")
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    action_url = db.Column(db.String(255), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
