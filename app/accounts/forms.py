"""Account & Asset forms."""
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, DecimalField, DateField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange, Optional

from app.models import ACCOUNT_TYPES, ASSET_TYPES


class AccountForm(FlaskForm):
    account_name = StringField(
        "Account name",
        validators=[DataRequired(), Length(min=2, max=80)],
    )
    account_type = SelectField(
        "Account type",
        validators=[DataRequired()],
        choices=[(t, t.replace("_", " ").title()) for t in ACCOUNT_TYPES],
    )
    current_balance = DecimalField(
        "Current balance (₹)",
        validators=[DataRequired(), NumberRange(min=0)],
        places=2,
    )
    submit = SubmitField("Save account")


class AssetForm(FlaskForm):
    asset_name = StringField(
        "Asset name",
        validators=[DataRequired(), Length(min=2, max=80)],
    )
    asset_type = SelectField(
        "Asset type",
        validators=[DataRequired()],
        choices=[(t, t.replace("_", " ").title()) for t in ASSET_TYPES],
    )
    current_value = DecimalField(
        "Current value (₹)",
        validators=[DataRequired(), NumberRange(min=0)],
        places=2,
    )
    purchase_value = DecimalField(
        "Purchase value (₹)",
        validators=[Optional(), NumberRange(min=0)],
        places=2,
    )
    purchase_date = DateField("Purchase date", validators=[Optional()])
    submit = SubmitField("Save asset")
