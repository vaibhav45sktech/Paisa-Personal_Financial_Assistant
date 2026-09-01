"""Application configuration."""
import os
from datetime import timedelta


class Config:
    """Base configuration."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")
    
    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres:postgres@localhost:5432/paisa_db",
    )
    
    # Render may provide postgres:// instead of postgresql://
    if database_url.startswith("postgres://"):
        database_url = database_url.replace(
            "postgres://",
            "postgresql://",
            1,
        )
    
    SQLALCHEMY_DATABASE_URI = database_url
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    

    # Sessions
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    REMEMBER_COOKIE_DURATION = timedelta(days=14)
    REMEMBER_COOKIE_HTTPONLY = True

    # CSRF (Flask-WTF)
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600

    # App-specific
    CURRENCY_SYMBOL = "₹"
    BUDGET_CATEGORIES = [
        "Grocery", "Transportation", "Electricity", "Water", "Gas",
        "Internet", "Phone Bill", "Rent", "EMI", "Insurance",
        "Healthcare", "Entertainment", "Shopping", "Miscellaneous",
    ]
    INCOME_TYPES = [
        "Monthly Salary", "Freelancer", "Business", "Student", "Other",
    ]
    PRIORITIES = ["High", "Medium", "Low"]

    # Onboarding profile selector — drives profile-aware scoring & dashboards.
    USER_TYPE_CHOICES = [
        ("student", "Student"),
        ("micro_entrepreneur", "Micro-Entrepreneur"),
        ("general", "General Personal Finance User"),
    ]


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": ProductionConfig,
}
