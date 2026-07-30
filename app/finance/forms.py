"""Finance forms — profile setup & goal creation."""
from decimal import Decimal

from flask import current_app
from flask_wtf import FlaskForm
from wtforms import (
    StringField, DecimalField, DateField, SelectField, FieldList, FormField,
    SubmitField, Form,
)
from wtforms.validators import DataRequired, NumberRange, Length, Optional


class FinancialProfileForm(FlaskForm):
    """Financial profile form. Budget category inputs are added dynamically
    from `Config.BUDGET_CATEGORIES` in the route."""

    income_type = SelectField("Income type", validators=[DataRequired()])
    monthly_gross_income = DecimalField(
        "Monthly gross income (₹)",
        validators=[
            DataRequired(message="Please enter your monthly income."),
            NumberRange(min=0, message="Income must be a positive number."),
        ],
        places=2,
    )
    submit = SubmitField("Save & continue")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.income_type.choices = [(x, x) for x in current_app.config["INCOME_TYPES"]]


class GoalEntryForm(Form):
    """Sub-form used inside GoalsForm (no CSRF token here — parent provides it).

    NOTE: The field is called `goal_name` (not `name`) because WTForms `FormField`
    itself has a built-in `name` attribute (the HTML name of the wrapper),
    which shadows the sub-field of the same name during template rendering.
    """

    goal_name = StringField(
        "Goal name",
        validators=[DataRequired(message="Enter a name."), Length(max=80)],
    )
    target_amount = DecimalField(
        "Target amount (₹)",
        validators=[
            DataRequired(message="Enter the target amount."),
            NumberRange(min=1, message="Amount must be greater than 0."),
        ],
        places=2,
    )
    target_date = DateField(
        "Target date",
        validators=[DataRequired(message="Pick a target date.")],
    )
    priority = SelectField(
        "Priority",
        validators=[DataRequired()],
        choices=[("High", "High"), ("Medium", "Medium"), ("Low", "Low")],
        default="Medium",
    )


class GoalsForm(FlaskForm):
    goals = FieldList(FormField(GoalEntryForm), min_entries=1)
    submit = SubmitField("Finish setup")
