"""Consent Center — view, grant and revoke data permissions.

Every route is scoped to `current_user`; a user can only ever read or change
their own consent rows.
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request

from flask_login import login_required, current_user

from app.models.consent import DATA_CATEGORIES, PURPOSES
from app.services import consent_service

consent_bp = Blueprint("consent", __name__, template_folder="../templates/consent")


@consent_bp.route("/")
@login_required
def index():
    consent_service.ensure_defaults(current_user.id)
    return render_template(
        "consent/index.html",
        matrix=consent_service.consent_matrix(current_user.id),
        summary=consent_service.summary(current_user.id),
    )


def _read_target() -> tuple[str | None, str | None, str | None]:
    """Pull and validate (purpose, category, scope) from the POST body."""
    purpose = (request.form.get("purpose") or "").strip()
    category = (request.form.get("data_category") or "").strip()
    scope = (request.form.get("scope") or "category").strip()

    if purpose not in PURPOSES:
        return None, None, None
    if scope == "purpose":
        return purpose, None, "purpose"
    if category not in DATA_CATEGORIES:
        return None, None, None
    return purpose, category, "category"


@consent_bp.route("/grant", methods=["POST"])
@login_required
def grant():
    purpose, category, scope = _read_target()
    if purpose is None:
        flash("That consent option isn't recognised.", "danger")
        return redirect(url_for("consent.index"))

    if scope == "purpose":
        consent_service.set_purpose(current_user.id, purpose, True)
        flash(f"Access granted for {consent_service.PURPOSE_LABELS[purpose]}.", "success")
    elif consent_service.grant(current_user.id, category, purpose):
        flash(
            f"{consent_service.CATEGORY_LABELS.get(category, category)} is now shared "
            f"with {consent_service.PURPOSE_LABELS[purpose]}.",
            "success",
        )
    else:
        flash("That data isn't used by this feature, so there's nothing to grant.", "warning")
    return redirect(url_for("consent.index"))


@consent_bp.route("/revoke", methods=["POST"])
@login_required
def revoke():
    purpose, category, scope = _read_target()
    if purpose is None:
        flash("That consent option isn't recognised.", "danger")
        return redirect(url_for("consent.index"))

    if scope == "purpose":
        consent_service.set_purpose(current_user.id, purpose, False)
        flash(
            f"{consent_service.PURPOSE_LABELS[purpose]} will no longer use your data.",
            "info",
        )
    elif consent_service.revoke(current_user.id, category, purpose):
        flash(
            f"{consent_service.CATEGORY_LABELS.get(category, category)} is no longer "
            f"used by {consent_service.PURPOSE_LABELS[purpose]}.",
            "info",
        )
    else:
        flash("That data isn't used by this feature, so there's nothing to revoke.", "warning")
    return redirect(url_for("consent.index"))
