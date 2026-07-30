"""Auth business logic — kept out of routes.

Now includes basic account-lockout: 5 failed attempts locks the account.
Admins/users can reset by editing the DB (or via a future password-reset flow).
"""
from datetime import datetime, timezone
from typing import Optional

from app.extensions import db
from app.models.user import User

MAX_FAILED_ATTEMPTS = 5


def register_user(username: str, email: str, phone: str, password: str) -> User:
    user = User(
        username=username.strip(),
        email=email.strip().lower(),
        phone=phone.strip(),
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def authenticate(identifier: str, password: str) -> tuple[Optional[User], Optional[str]]:
    """Return (user_or_None, error_reason_or_None)."""
    identifier = (identifier or "").strip()
    if not identifier:
        return None, "Please enter your username or email."

    user = User.query.filter(
        (User.email == identifier.lower()) | (User.username == identifier)
    ).first()

    if user is None:
        return None, "Invalid username/email or password."

    if user.is_locked:
        return None, "Your account is locked after too many failed attempts. Reset via the DB or password-reset flow."

    if not user.check_password(password):
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
            user.is_locked = True
        db.session.commit()
        return None, "Invalid username/email or password."

    # Success
    user.failed_login_attempts = 0
    user.is_locked = False
    user.last_login = datetime.now(timezone.utc)
    db.session.commit()
    return user, None
