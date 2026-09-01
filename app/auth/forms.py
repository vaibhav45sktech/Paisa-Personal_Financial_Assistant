"""Auth forms — Flask-WTF with server-side validation & CSRF protection."""
from flask import current_app
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, SubmitField
from wtforms.validators import (
    DataRequired, Length, Email, EqualTo, Regexp, ValidationError,
)

from app.models.user import User


class SignupForm(FlaskForm):
    username = StringField(
        "Username",
        validators=[
            DataRequired(),
            Length(min=3, max=30, message="Username must be 3–30 characters."),
            Regexp(
                r"^[A-Za-z0-9_\-]+$",
                message="Only letters, numbers, underscore and hyphen allowed.",
            ),
        ],
    )
    email = StringField(
        "Email",
        validators=[
            DataRequired(),
            Email(message="Please enter a valid email address."),
            Length(max=255),
        ],
    )
    phone = StringField(
        "Phone number",
        validators=[
            DataRequired(),
            Length(min=6, max=20, message="Phone number looks too short/long."),
            Regexp(
                r"^[+0-9\s\-]+$",
                message="Only digits, spaces, + and - are allowed.",
            ),
        ],
    )
    user_type = SelectField(
        "I am a",
        validators=[DataRequired(message="Please pick the option that fits you best.")],
        default="general",
    )
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(),
            Length(min=6, max=128, message="Password must be at least 6 characters."),
        ],
    )
    confirm = PasswordField(
        "Confirm password",
        validators=[
            DataRequired(),
            EqualTo("password", message="Passwords do not match."),
        ],
    )
    submit = SubmitField("Create account")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_type.choices = current_app.config["USER_TYPE_CHOICES"]

    def validate_username(self, field):
        if User.query.filter_by(username=field.data.strip()).first():
            raise ValidationError("This username is already taken.")

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.strip().lower()).first():
            raise ValidationError("An account with this email already exists.")


class LoginForm(FlaskForm):
    identifier = StringField(
        "Username or Email",
        validators=[DataRequired(), Length(max=255)],
    )
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Log in")
