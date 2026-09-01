"""Shared pytest fixtures.

Tests run against a real PostgreSQL database (the models use postgresql.UUID,
which SQLite can't provide). Point PAISA_TEST_DATABASE_URL at a throwaway DB;
the schema is created and dropped per session.
"""
import os
import uuid

import pytest

from app import create_app
from app.extensions import db as _db
from app.models.user import User
from app.services import consent_service

TEST_DATABASE_URL = os.environ.get(
    "PAISA_TEST_DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/paisa_test",
)


@pytest.fixture(scope="session")
def app():
    # The URI must be swapped BEFORE create_app: Flask-SQLAlchemy binds its
    # engine inside init_app, so a post-hoc config update would leave the
    # engine pointed at the development database — and drop_all would wipe it.
    from config import DevelopmentConfig
    DevelopmentConfig.SQLALCHEMY_DATABASE_URI = TEST_DATABASE_URL

    application = create_app("development")
    application.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        RATELIMIT_ENABLED=False,
    )

    # Belt and braces: never let a misconfigured run drop a real database.
    active = application.config["SQLALCHEMY_DATABASE_URI"]
    if active != TEST_DATABASE_URL or "test" not in active:
        raise RuntimeError(
            f"Refusing to run: tests would target {active!r}, "
            f"which is not the designated test database."
        )

    with application.app_context():
        _db.drop_all()
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def db(app):
    """Roll every test back so cases stay independent."""
    yield _db
    _db.session.rollback()
    for table in reversed(_db.metadata.sorted_tables):
        _db.session.execute(table.delete())
    _db.session.commit()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def make_user(db):
    """Factory for a persisted user with a full default consent matrix."""
    def _make(user_type="general", *, with_consents=True, **kwargs):
        suffix = uuid.uuid4().hex[:8]
        user = User(
            username=kwargs.pop("username", f"user_{suffix}"),
            email=kwargs.pop("email", f"{suffix}@example.test"),
            phone=kwargs.pop("phone", "+919000000000"),
            user_type=user_type,
            **kwargs,
        )
        user.set_password("test-password")
        db.session.add(user)
        db.session.commit()
        if with_consents:
            consent_service.ensure_defaults(user.id, source="onboarding")
        return user
    return _make
