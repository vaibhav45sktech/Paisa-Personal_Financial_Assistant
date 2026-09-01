"""Application factory."""
import os
from dotenv import load_dotenv
from flask import Flask, render_template

from config import config_by_name
from app.extensions import db, migrate, login_manager, bcrypt, csrf, limiter


def create_app(config_name: str | None = None) -> Flask:
    load_dotenv()

    app = Flask(__name__, template_folder="templates", static_folder="static")
    config_name = config_name or os.environ.get("FLASK_ENV", "default")
    app.config.from_object(config_by_name.get(config_name, config_by_name["default"]))

    # Extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    # Register user loader (imported here to avoid circular imports)
    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, user_id)

    # Blueprints
    from app.main.routes import main_bp
    from app.auth.routes import auth_bp
    from app.finance.routes import finance_bp
    from app.dashboard.routes import dashboard_bp
    from app.accounts.routes import accounts_bp
    from app.statements.routes import statements_bp
    from app.budgets.routes import budgets_bp
    from app.ai_coach.routes import ai_coach_bp
    from app.analyzer.routes import analyzer_bp
    from app.notifications.routes import notifications_bp
    from app.reports.routes import reports_bp
    from app.consent.routes import consent_bp
    from app.recommendations.routes import recommendations_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(finance_bp, url_prefix="/finance")
    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")
    app.register_blueprint(accounts_bp, url_prefix="/accounts")
    app.register_blueprint(statements_bp, url_prefix="/statements")
    app.register_blueprint(budgets_bp, url_prefix="/budgets")
    app.register_blueprint(ai_coach_bp, url_prefix="/coach")
    app.register_blueprint(analyzer_bp, url_prefix="/analyzer")
    app.register_blueprint(notifications_bp, url_prefix="/notifications")
    app.register_blueprint(reports_bp, url_prefix="/reports")
    app.register_blueprint(consent_bp, url_prefix="/consent")
    app.register_blueprint(recommendations_bp, url_prefix="/recommendations")

    # Expose unread notification count to every template
    from app.services import notification_service
    from flask_login import current_user
    @app.context_processor
    def inject_notifications():
        if current_user.is_authenticated:
            return {"unread_notifications": notification_service.unread_count(current_user)}
        return {"unread_notifications": 0}

    # Jinja filter for INR formatting
    @app.template_filter("inr")
    def inr_filter(value):
        try:
            n = float(value or 0)
        except (TypeError, ValueError):
            n = 0
        # Indian numbering (1,50,000)
        s = f"{int(round(n)):,}"
        # Convert 1,500,000 -> 15,00,000 style (Indian grouping)
        parts = s.split(",")
        if len(parts) > 2:
            last = parts[-1]
            other = "".join(parts[:-1])
            grouped = []
            while len(other) > 2:
                grouped.insert(0, other[-2:])
                other = other[:-2]
            if other:
                grouped.insert(0, other)
            s = ",".join(grouped) + "," + last
        return f"{app.config['CURRENCY_SYMBOL']}{s}"

    # Error pages
    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("errors/500.html"), 500

    return app
