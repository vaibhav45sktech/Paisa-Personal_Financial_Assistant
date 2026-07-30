"""Asset model — cash / FD / gold / property / stocks / crypto / mutual_funds."""
import uuid
from datetime import datetime, timezone, date

from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db

ASSET_TYPES = (
    "cash", "fixed_deposit", "gold", "property",
    "stocks", "crypto", "mutual_funds",
)


class Asset(db.Model):
    __tablename__ = "assets"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    asset_name = db.Column(db.String(80), nullable=False)
    asset_type = db.Column(db.String(20), nullable=False, default="cash")
    current_value = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    purchase_value = db.Column(db.Numeric(14, 2), nullable=True)
    purchase_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = db.relationship("User", back_populates="assets")

    def __repr__(self) -> str:
        return f"<Asset {self.asset_name}>"
