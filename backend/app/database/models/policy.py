from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Numeric, Integer, Boolean, ForeignKey
from .base import TimeStampedBase, generate_uuid
from typing import Optional

class Policy(TimeStampedBase):
    __tablename__ = "policies"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    name: Mapped[str] = mapped_column(String, default="Default Commerce Policy")
    version: Mapped[int] = mapped_column(Integer, default=1, index=True)
    max_transaction_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("10000.00"))
    approval_threshold: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("5000.00"))
    low_risk_limit: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("2000.00"))
    max_discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("5.00"))
    max_quantity: Mapped[int] = mapped_column(Integer, default=5)
    allowed_currency: Mapped[str] = mapped_column(String, default="INR")
    auto_approval_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    authorization_expiration_minutes: Mapped[int] = mapped_column(Integer, default=10)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by_user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)

    merchant = relationship("Merchant")
    created_by = relationship("User")

    def to_snapshot(self) -> dict:
        """Returns an immutable dictionary snapshot of evaluated policy values."""
        return {
            "policy_id": self.id,
            "policy_version": self.version,
            "name": self.name,
            "max_transaction_amount": str(self.max_transaction_amount),
            "approval_threshold": str(self.approval_threshold),
            "low_risk_limit": str(self.low_risk_limit),
            "max_discount_percent": str(self.max_discount_percent),
            "max_quantity": self.max_quantity,
            "allowed_currency": self.allowed_currency,
            "auto_approval_enabled": self.auto_approval_enabled,
            "authorization_expiration_minutes": self.authorization_expiration_minutes
        }
