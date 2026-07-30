"""Category model — user-scoped or system-default (user_id NULL)."""
import uuid

from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db

CATEGORY_TYPES = ("income", "expense", "transfer")

# Seeded on first-run for every user (via services.seed_default_categories).
DEFAULT_CATEGORIES = [
    # (name, type, icon, color)
    ("Salary", "income", "bi-cash-coin", "#22C55E"),
    ("Freelance", "income", "bi-briefcase", "#10B981"),
    ("Interest", "income", "bi-bank", "#06B6D4"),
    ("Refund", "income", "bi-arrow-counterclockwise", "#84CC16"),

    ("Grocery", "expense", "bi-basket", "#F97316"),
    ("Transportation", "expense", "bi-car-front", "#EF4444"),
    ("Electricity", "expense", "bi-lightning-charge", "#EAB308"),
    ("Water", "expense", "bi-droplet", "#3B82F6"),
    ("Gas", "expense", "bi-fire", "#F43F5E"),
    ("Internet", "expense", "bi-wifi", "#8B5CF6"),
    ("Phone Bill", "expense", "bi-phone", "#EC4899"),
    ("Rent", "expense", "bi-house-door", "#F59E0B"),
    ("EMI", "expense", "bi-credit-card-2-back", "#DC2626"),
    ("Insurance", "expense", "bi-shield-check", "#0EA5E9"),
    ("Healthcare", "expense", "bi-heart-pulse", "#E11D48"),
    ("Entertainment", "expense", "bi-film", "#A855F7"),
    ("Shopping", "expense", "bi-bag", "#F472B6"),
    ("Dining", "expense", "bi-cup-hot", "#FB923C"),
    ("Subscriptions", "expense", "bi-arrow-repeat", "#6366F1"),
    ("Miscellaneous", "expense", "bi-three-dots", "#78716C"),

    ("Transfer", "transfer", "bi-arrow-left-right", "#6B7280"),
]


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    name = db.Column(db.String(50), nullable=False)
    type = db.Column(db.String(10), nullable=False)
    icon = db.Column(db.String(40), nullable=True)
    color = db.Column(db.String(9), nullable=True)

    __table_args__ = (
        db.UniqueConstraint("user_id", "name", name="uq_user_category_name"),
    )

    def __repr__(self) -> str:
        return f"<Category {self.name} ({self.type})>"
