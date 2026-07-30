"""Statement ingestion routes — upload → review → confirm."""
from flask import (
    Blueprint, render_template, redirect, url_for, flash, request, abort,
)
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Account, BankStatement, Transaction, Category
from app.statements.forms import UploadStatementForm
from app.services import statement_service, parser_service

statements_bp = Blueprint(
    "statements", __name__, template_folder="../templates/statements"
)


@statements_bp.route("/")
@login_required
def index():
    stmts = (
        BankStatement.query.filter_by(user_id=current_user.id)
        .order_by(BankStatement.upload_date.desc())
        .all()
    )
    return render_template("statements/index.html", statements=stmts)


@statements_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if not current_user.accounts:
        flash("Add an account first so we know where the statement belongs.", "warning")
        return redirect(url_for("accounts.new_account"))

    form = UploadStatementForm()
    form.account_id.choices = [
        (str(a.id), f"{a.account_name} ({a.account_type.replace('_',' ').title()})")
        for a in current_user.accounts
    ]

    if form.validate_on_submit():
        account = Account.query.filter_by(
            id=form.account_id.data, user_id=current_user.id
        ).first_or_404()

        f = form.statement.data
        try:
            # Seed default categories on first upload so auto-categorization has somewhere to land
            statement_service.seed_default_categories(current_user)
            stmt = statement_service.import_csv(current_user, account, f.stream, f.filename)
        except parser_service.StatementParseError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("statements.upload"))

        flash(
            f"Extracted {stmt.total_records_extracted} transactions. "
            "Review below and confirm the ones you'd like to import.",
            "success",
        )
        return redirect(url_for("statements.review", statement_id=stmt.id))

    return render_template("statements/upload.html", form=form)


@statements_bp.route("/<uuid:statement_id>/review", methods=["GET"])
@login_required
def review(statement_id):
    stmt = BankStatement.query.filter_by(
        id=statement_id, user_id=current_user.id
    ).first_or_404()
    txns = (
        Transaction.query.filter_by(statement_id=stmt.id, user_id=current_user.id)
        .order_by(Transaction.date.desc())
        .all()
    )
    cats = (
        Category.query.filter(
            (Category.user_id == current_user.id) | (Category.user_id.is_(None))
        )
        .order_by(Category.type, Category.name)
        .all()
    )
    return render_template(
        "statements/review.html", statement=stmt, transactions=txns, categories=cats
    )


@statements_bp.route("/<uuid:statement_id>/confirm", methods=["POST"])
@login_required
def confirm(statement_id):
    stmt = BankStatement.query.filter_by(
        id=statement_id, user_id=current_user.id
    ).first_or_404()

    action = request.form.get("action", "confirm")
    selected_ids = request.form.getlist("txn_ids")

    if not selected_ids:
        flash("No transactions selected.", "warning")
        return redirect(url_for("statements.review", statement_id=stmt.id))

    if action == "ignore":
        n = statement_service.ignore_transactions(current_user, selected_ids)
        flash(f"Ignored {n} transaction(s).", "info")
    else:
        result = statement_service.confirm_transactions(current_user, selected_ids)
        flash(
            f"Confirmed {result['expenses']} expense(s) and {result['income']} income record(s). "
            "Account balances updated.",
            "success",
        )
    return redirect(url_for("statements.review", statement_id=stmt.id))


@statements_bp.route("/txn/<uuid:txn_id>/reclassify", methods=["POST"])
@login_required
def reclassify(txn_id):
    """Change a transaction's category or kind before confirming."""
    category_id = request.form.get("category_id") or None
    kind = request.form.get("kind") or None
    statement_service.update_transaction(current_user, txn_id, category_id=category_id, kind=kind)
    stmt_id = request.form.get("statement_id")
    return redirect(url_for("statements.review", statement_id=stmt_id))
