"""Purchase Impact Analyzer routes."""
from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, DecimalField, IntegerField, SubmitField
from wtforms.validators import DataRequired, NumberRange

from app.services import analyzer_service

analyzer_bp = Blueprint("analyzer", __name__, template_folder="../templates/analyzer")


class PurchaseForm(FlaskForm):
    product_name = StringField("What are you planning to buy?", validators=[DataRequired()])
    product_price = DecimalField("Total price (₹)", validators=[DataRequired(), NumberRange(min=1)], places=2)
    down_payment = DecimalField("Down payment (₹)", validators=[NumberRange(min=0)], default=0, places=2)
    tenure_months = IntegerField("Loan tenure (months)", validators=[NumberRange(min=0)], default=0)
    interest_rate = DecimalField("Interest rate (% per year)", validators=[NumberRange(min=0, max=50)], default=0, places=2)
    submit = SubmitField("Analyze impact")


@analyzer_bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    form = PurchaseForm()
    result = None
    if form.validate_on_submit():
        result = analyzer_service.analyze(
            current_user,
            product_name=form.product_name.data.strip(),
            product_price=float(form.product_price.data),
            down_payment=float(form.down_payment.data or 0),
            tenure_months=int(form.tenure_months.data or 0),
            interest_rate=float(form.interest_rate.data or 0),
        )
    return render_template("analyzer/index.html", form=form, result=result)
