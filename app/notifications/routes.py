"""Notification routes."""
from flask import Blueprint, render_template, redirect, url_for, request
from flask_login import login_required, current_user

from app.services import notification_service

notifications_bp = Blueprint("notifications", __name__, template_folder="../templates/notifications")


@notifications_bp.route("/")
@login_required
def index():
    items = notification_service.list_for(current_user)
    return render_template("notifications/list.html", notifications=items)


@notifications_bp.route("/<uuid:notification_id>/read", methods=["POST"])
@login_required
def mark_read(notification_id):
    notification_service.mark_read(current_user, notification_id)
    return redirect(request.referrer or url_for("notifications.index"))


@notifications_bp.route("/read-all", methods=["POST"])
@login_required
def mark_all():
    notification_service.mark_all_read(current_user)
    return redirect(url_for("notifications.index"))
