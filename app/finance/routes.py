"""Finance routes — profile setup, goals setup."""
from decimal import Decimal, InvalidOperation

from flask import (
    Blueprint, render_template, redirect, url_for, flash, request, current_app,
    abort,
)
from flask_login import login_required, current_user

from app.finance.forms import FinancialProfileForm, GoalsForm, GoalEntryForm
from app.finance.services import upsert_profile, add_goals, delete_goal

finance_bp = Blueprint("finance", __name__, template_folder="../templates/finance")


def _parse_budget_from_form() -> dict[str, Decimal]:
    """Parse the dynamic `budget[<Category>]` inputs from the POSTed form."""
    budget: dict[str, Decimal] = {}
    for category in current_app.config["BUDGET_CATEGORIES"]:
        raw = request.form.get(f"budget[{category}]", "").strip()
        if raw == "":
            budget[category] = Decimal("0")
            continue
        try:
            value = Decimal(raw)
            if value < 0:
                raise InvalidOperation
            budget[category] = value
        except (InvalidOperation, ValueError):
            budget[category] = Decimal("0")
    return budget


@finance_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile_setup():
    profile = current_user.profile
    form = FinancialProfileForm()

    if request.method == "GET" and profile:
        form.income_type.data = profile.income_type
        form.monthly_gross_income.data = profile.monthly_gross_income

    if form.validate_on_submit():
        budget = _parse_budget_from_form()
        upsert_profile(
            current_user,
            income_type=form.income_type.data,
            monthly_gross_income=form.monthly_gross_income.data,
            budget=budget,
        )
        flash("Financial profile saved.", "success")
        if not current_user.goals:
            return redirect(url_for("finance.goals_setup"))
        return redirect(url_for("dashboard.index"))

    return render_template(
        "finance/profile_setup.html",
        form=form,
        profile=profile,
        categories=current_app.config["BUDGET_CATEGORIES"],
    )


@finance_bp.route("/goals", methods=["GET", "POST"])
@login_required
def goals_setup():
    if not current_user.profile:
        flash("Please set up your financial profile first.", "warning")
        return redirect(url_for("finance.profile_setup"))

    form = GoalsForm()

    if form.validate_on_submit():
        entries = [
            {
                "name": g.goal_name.data,
                "target_amount": g.target_amount.data,
                "target_date": g.target_date.data,
                "priority": g.priority.data,
            }
            for g in form.goals
        ]
        add_goals(current_user, entries)
        flash(f"Added {len(entries)} goal(s).", "success")
        return redirect(url_for("dashboard.index"))

    return render_template(
        "finance/goals_setup.html",
        form=form,
        priorities=current_app.config["PRIORITIES"],
    )


@finance_bp.route("/goals/<uuid:goal_id>/delete", methods=["POST"])
@login_required
def delete_goal_view(goal_id):
    if not delete_goal(current_user, goal_id):
        abort(404)
    flash("Goal removed.", "info")
    return redirect(url_for("dashboard.index"))
