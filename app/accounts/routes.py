"""Accounts & Assets routes."""
from flask import Blueprint, render_template, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Account, Asset
from app.accounts.forms import AccountForm, AssetForm

accounts_bp = Blueprint("accounts", __name__, template_folder="../templates/accounts")


# ---------- Accounts ----------

@accounts_bp.route("/")
@login_required
def index():
    return render_template(
        "accounts/index.html",
        accounts=current_user.accounts,
        assets=current_user.assets,
    )


@accounts_bp.route("/new", methods=["GET", "POST"])
@login_required
def new_account():
    form = AccountForm()
    if form.validate_on_submit():
        acc = Account(
            user_id=current_user.id,
            account_name=form.account_name.data.strip(),
            account_type=form.account_type.data,
            current_balance=form.current_balance.data,
        )
        db.session.add(acc)
        db.session.commit()
        flash("Account added.", "success")
        return redirect(url_for("accounts.index"))
    return render_template("accounts/new_account.html", form=form)


@accounts_bp.route("/<uuid:account_id>/delete", methods=["POST"])
@login_required
def delete_account(account_id):
    acc = Account.query.filter_by(id=account_id, user_id=current_user.id).first_or_404()
    db.session.delete(acc)
    db.session.commit()
    flash("Account removed.", "info")
    return redirect(url_for("accounts.index"))


# ---------- Assets ----------

@accounts_bp.route("/assets/new", methods=["GET", "POST"])
@login_required
def new_asset():
    form = AssetForm()
    if form.validate_on_submit():
        a = Asset(
            user_id=current_user.id,
            asset_name=form.asset_name.data.strip(),
            asset_type=form.asset_type.data,
            current_value=form.current_value.data,
            purchase_value=form.purchase_value.data,
            purchase_date=form.purchase_date.data,
        )
        db.session.add(a)
        db.session.commit()
        flash("Asset added.", "success")
        return redirect(url_for("accounts.index"))
    return render_template("accounts/new_asset.html", form=form)


@accounts_bp.route("/assets/<uuid:asset_id>/delete", methods=["POST"])
@login_required
def delete_asset(asset_id):
    a = Asset.query.filter_by(id=asset_id, user_id=current_user.id).first_or_404()
    db.session.delete(a)
    db.session.commit()
    flash("Asset removed.", "info")
    return redirect(url_for("accounts.index"))
