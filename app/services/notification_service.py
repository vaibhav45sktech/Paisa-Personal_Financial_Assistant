"""Notification helpers — create, list, mark-as-read."""
from __future__ import annotations

from datetime import date

from app.extensions import db
from app.models import Notification


def create(user, *, title: str, message: str,
           type: str = "info", priority: str = "medium",
           action_url: str | None = None) -> Notification:
    n = Notification(
        user_id=user.id, title=title, message=message,
        type=type, priority=priority, action_url=action_url,
    )
    db.session.add(n)
    db.session.commit()
    return n


def list_for(user, *, unread_only: bool = False):
    q = Notification.query.filter_by(user_id=user.id)
    if unread_only:
        q = q.filter_by(is_read=False)
    return q.order_by(Notification.created_at.desc()).limit(50).all()


def unread_count(user) -> int:
    return Notification.query.filter_by(user_id=user.id, is_read=False).count()


def mark_read(user, notification_id: str) -> bool:
    n = Notification.query.filter_by(id=notification_id, user_id=user.id).first()
    if not n:
        return False
    n.is_read = True
    db.session.commit()
    return True


def mark_all_read(user) -> int:
    q = Notification.query.filter_by(user_id=user.id, is_read=False)
    n = 0
    for row in q:
        row.is_read = True
        n += 1
    db.session.commit()
    return n
