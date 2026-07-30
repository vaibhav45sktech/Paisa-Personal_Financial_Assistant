"""Purchase Impact Analyzer — EMI, affordability, recommendations.

Everything is dynamically computed. Nothing is stored.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from app.services import dashboard_service


def compute_emi(loan_amount: float, annual_rate_pct: float, tenure_months: int) -> float:
    """Standard reducing-balance EMI."""
    if tenure_months <= 0 or loan_amount <= 0:
        return 0.0
    r = (annual_rate_pct / 100) / 12.0
    if r == 0:
        return loan_amount / tenure_months
    n = tenure_months
    return loan_amount * r * (1 + r) ** n / ((1 + r) ** n - 1)


def analyze(user, product_name: str, product_price: float,
            down_payment: float, tenure_months: int, interest_rate: float,
            *, today=None) -> dict:
    """Full impact analysis. Live income/expenses come from the user's ledger."""
    from datetime import date
    today = today or date.today()

    loan_amount = max(0.0, product_price - down_payment)
    emi = compute_emi(loan_amount, interest_rate, tenure_months)

    monthly = dashboard_service.monthly_totals(user, today.month, today.year)
    income = monthly["income"] or (float(user.profile.monthly_gross_income) if user.profile else 0.0)
    expenses = monthly["expenses"]
    current_savings = income - expenses
    savings_after_emi = current_savings - emi

    # Debt-to-Income proxy: emi + existing EMI-category spend
    dti_new = (emi / income * 100) if income > 0 else 0.0

    if income <= 0:
        status = "unknown"
        recommendation = "Add income data (upload a statement or log income) to get a proper affordability read."
    elif dti_new <= 25 and savings_after_emi >= 0.15 * income:
        status = "affordable"
        recommendation = f"Green light. EMI is {dti_new:.1f}% of income and you'd still save 15%+ per month."
    elif dti_new <= 40 and savings_after_emi > 0:
        status = "borderline"
        recommendation = f"Doable but tight — EMI would eat {dti_new:.1f}% of your income. Consider a shorter tenure or higher down payment."
    else:
        status = "danger"
        recommendation = f"Too much strain — EMI would be {dti_new:.1f}% of income and cut deep into savings. Increase down payment or delay."

    total_interest = (emi * tenure_months) - loan_amount if tenure_months > 0 else 0.0
    total_cost = product_price + total_interest

    return {
        "product_name": product_name,
        "product_price": product_price,
        "down_payment": down_payment,
        "loan_amount": loan_amount,
        "tenure_months": tenure_months,
        "interest_rate": interest_rate,
        "emi": round(emi, 2),
        "monthly_income": round(income, 2),
        "monthly_expenses": round(expenses, 2),
        "current_savings": round(current_savings, 2),
        "savings_after_emi": round(savings_after_emi, 2),
        "dti_new_pct": round(dti_new, 1),
        "total_interest": round(total_interest, 2),
        "total_cost": round(total_cost, 2),
        "status": status,
        "recommendation": recommendation,
    }
