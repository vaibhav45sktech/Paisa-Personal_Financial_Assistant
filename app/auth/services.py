"""Auth business logic — kept out of routes.

Now includes basic account-lockout: 5 failed attempts locks the account.
Admins/users can reset by editing the DB (or via a future password-reset flow).
"""
from datetime import datetime, timezone
from typing import Optional

from app.extensions import db
from app.models.user import User, USER_TYPES
from app.services import consent_service

MAX_FAILED_ATTEMPTS = 5


def register_user(
    username: str, email: str, phone: str, password: str,
    user_type: str = "general",
) -> User:
    user = User(
        username=username.strip(),
        email=email.strip().lower(),
        phone=phone.strip(),
        user_type=user_type if user_type in USER_TYPES else "general",
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    # Seed the consent matrix so the app's existing features work from signup.
    # The user can revoke any of it from the Consent Center.
    consent_service.ensure_defaults(user.id, source="onboarding")
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
