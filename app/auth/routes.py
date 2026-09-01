"""Auth routes — signup, login, logout with rate limiting + lockout."""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user

from app.extensions import limiter
from app.auth.forms import SignupForm, LoginForm
from app.auth.services import register_user, authenticate

auth_bp = Blueprint("auth", __name__, template_folder="../templates/auth")


@auth_bp.route("/signup", methods=["GET", "POST"])
@limiter.limit("10 per hour")
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    form = SignupForm()
    if form.validate_on_submit():
        user = register_user(
            username=form.username.data,
            email=form.email.data,
            phone=form.phone.data,
            password=form.password.data,
            user_type=form.user_type.data,
        )
        login_user(user)
        flash("Welcome to paisa!", "success")
        return redirect(url_for("finance.profile_setup"))
    return render_template("auth/signup.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("20 per hour")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    form = LoginForm()
    if form.validate_on_submit():
        user, err = authenticate(form.identifier.data, form.password.data)
        if user is None:
            flash(err or "Invalid credentials.", "danger")
            return render_template("auth/login.html", form=form), 401
        login_user(user, remember=True)
        next_url = request.args.get("next") or url_for("dashboard.index")
        return redirect(next_url)
    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You've been logged out.", "info")
    return redirect(url_for("main.landing"))
