"""Finance business logic — profile & goals."""
from decimal import Decimal
from typing import Iterable

from app.extensions import db
from app.models.financial_profile import FinancialProfile, BudgetItem
from app.models.financial_goal import FinancialGoal
from app.models.user import User


def upsert_profile(
    user: User,
    income_type: str,
    monthly_gross_income: Decimal,
    budget: dict[str, Decimal],
) -> FinancialProfile:
    """Create or update a user's financial profile + budget items."""
    profile = user.profile
    if profile is None:
        profile = FinancialProfile(user_id=user.id)
        db.session.add(profile)

    profile.income_type = income_type
    profile.monthly_gross_income = monthly_gross_income

    # Reset budget items and rewrite from input
    existing = {b.category: b for b in profile.budget_items}
    for category, amount in budget.items():
        amt = Decimal(amount or 0)
        if category in existing:
            existing[category].amount = amt
        else:
            profile.budget_items.append(BudgetItem(category=category, amount=amt))

    # Remove categories that weren't submitted
    for category, item in list(existing.items()):
        if category not in budget:
            db.session.delete(item)

    db.session.commit()
    return profile


def add_goals(user: User, goal_entries: Iterable[dict]) -> list[FinancialGoal]:
    """Persist multiple goals for the user."""
    created = []
    for entry in goal_entries:
        goal = FinancialGoal(
            user_id=user.id,
            name=entry["name"].strip(),
            target_amount=Decimal(entry["target_amount"]),
            target_date=entry["target_date"],
            priority=entry["priority"],
        )
        db.session.add(goal)
        created.append(goal)
    db.session.commit()
    return created


def delete_goal(user: User, goal_id: str) -> bool:
    goal = FinancialGoal.query.filter_by(id=goal_id, user_id=user.id).first()
    if not goal:
        return False
    db.session.delete(goal)
    db.session.commit()
    return True
