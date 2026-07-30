"""Model package — imports all models so Flask-Migrate can detect them."""
from app.models.user import User
from app.models.financial_profile import FinancialProfile, BudgetItem
from app.models.financial_goal import FinancialGoal
from app.models.account import Account, ACCOUNT_TYPES
from app.models.asset import Asset, ASSET_TYPES
from app.models.category import Category, DEFAULT_CATEGORIES, CATEGORY_TYPES
from app.models.statement import BankStatement, STATEMENT_STATUS
from app.models.transaction import Transaction, TRANSACTION_TYPES, TRANSACTION_STATUS
from app.models.budget import Budget
from app.models.ledger import Expense, Income
from app.models.notification import Notification, NOTIFICATION_TYPES, NOTIFICATION_PRIORITIES
from app.models.purchase import Purchase
from app.models.ai_conversation import AISession, AIMessage

__all__ = [
    "User", "FinancialProfile", "BudgetItem", "FinancialGoal",
    "Account", "ACCOUNT_TYPES", "Asset", "ASSET_TYPES",
    "Category", "DEFAULT_CATEGORIES", "CATEGORY_TYPES",
    "BankStatement", "STATEMENT_STATUS",
    "Transaction", "TRANSACTION_TYPES", "TRANSACTION_STATUS",
    "Budget", "Expense", "Income",
    "Notification", "NOTIFICATION_TYPES", "NOTIFICATION_PRIORITIES",
    "Purchase", "AISession", "AIMessage",
]
