"""Budget routes — set monthly budget per expense category."""
from datetime import date

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Category, Budget
from app.services import dashboard_service, statement_service

budgets_bp = Blueprint("budgets", __name__, template_folder="../templates/budgets")


@budgets_bp.route("/", methods=["GET"])
@login_required
def index():
    today = date.today()
    month = int(request.args.get("month", today.month))
    year = int(request.args.get("year", today.year))

    # Ensure category set exists (idempotent)
    statement_service.seed_default_categories(current_user)

    expense_cats = (
        Category.query.filter(
            ((Category.user_id == current_user.id) | (Category.user_id.is_(None))),
            Category.type == "expense",
        )
        .order_by(Category.name)
        .all()
    )
    budgets = {
        b.category_id: b for b in
        Budget.query.filter_by(user_id=current_user.id, month=month, year=year).all()
    }
    rows = actual_vs_budget = dashboard_service.actual_vs_budget(current_user, month, year)
    totals = dashboard_service.monthly_totals(current_user, month, year)

    return render_template(
        "budgets/index.html",
        month=month, year=year,
        categories=expense_cats, budgets=budgets,
        rows=rows, totals=totals,
    )


@budgets_bp.route("/save", methods=["POST"])
@login_required
def save():
    month = int(request.form.get("month"))
    year = int(request.form.get("year"))

    expense_cats = Category.query.filter(
        ((Category.user_id == current_user.id) | (Category.user_id.is_(None))),
        Category.type == "expense",
    ).all()

    for cat in expense_cats:
        raw = (request.form.get(f"budget[{cat.id}]") or "").strip()
        amount = 0
        try:
            amount = float(raw) if raw else 0
        except ValueError:
            amount = 0
        b = Budget.query.filter_by(
            user_id=current_user.id, category_id=cat.id, month=month, year=year
        ).first()
        if amount <= 0:
            if b:
                db.session.delete(b)
            continue
        if b is None:
            b = Budget(user_id=current_user.id, category_id=cat.id, month=month, year=year, budgeted_amount=amount)
            db.session.add(b)
        else:
            b.budgeted_amount = amount

    db.session.commit()
    flash("Budgets saved.", "success")
    return redirect(url_for("budgets.index", month=month, year=year))
