"""Print-friendly / PDF report routes.

Uses browser print (Ctrl/Cmd+P → Save as PDF) to keep dependencies minimal.
The page is styled with a `.print-report` layout that prints cleanly.
"""
from datetime import date

from flask import Blueprint, render_template
from flask_login import login_required, current_user

from app.services import health_engine, dashboard_service

reports_bp = Blueprint("reports", __name__, template_folder="../templates/reports")


@reports_bp.route("/")
@login_required
def index():
    today = date.today()
    health = health_engine.compute_health_score(current_user, today=today)
    nw = health_engine.compute_net_worth(current_user)
    avb = dashboard_service.actual_vs_budget(current_user, today.month, today.year)
    monthly = dashboard_service.monthly_totals(current_user, today.month, today.year)

    return render_template(
        "reports/index.html",
        health=health, net_worth=nw, actual_vs_budget=avb, monthly=monthly,
        today=today,
    )
