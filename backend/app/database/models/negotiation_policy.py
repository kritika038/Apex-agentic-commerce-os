from decimal import Decimal
from typing import Optional, List
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Numeric, Integer, Boolean, ForeignKey, JSON
from .base import TimeStampedBase, generate_uuid


class MerchantNegotiationPolicy(TimeStampedBase):
    __tablename__ = "merchant_negotiation_policies"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    tenant_id: Mapped[str] = mapped_column(String, index=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    name: Mapped[str] = mapped_column(String, default="Standard Price Negotiation Policy")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    
    # Discount limits
    max_discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("5.00"))
    max_discount_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True, default=Decimal("1000.00"))
    auto_accept_below_discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("3.00"))
    approval_above_discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("3.00"))
    
    # Order thresholds & limits
    max_quantity: Mapped[int] = mapped_column(Integer, default=5)
    min_order_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("1000.00"))
    
    # Scoping
    allowed_categories: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True, default=list)
    allowed_products: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True, default=list)
    
    currency: Mapped[str] = mapped_column(String, default="INR")
    offer_ttl_minutes: Mapped[int] = mapped_column(Integer, default=10)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    merchant = relationship("Merchant")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "merchant_id": self.merchant_id,
            "name": self.name,
            "enabled": self.enabled,
            "max_discount_percent": float(self.max_discount_percent),
            "max_discount_amount": float(self.max_discount_amount) if self.max_discount_amount else None,
            "auto_accept_below_discount_percent": float(self.auto_accept_below_discount_percent),
            "approval_above_discount_percent": float(self.approval_above_discount_percent),
            "max_quantity": self.max_quantity,
            "min_order_value": float(self.min_order_value),
            "allowed_categories": self.allowed_categories or [],
            "allowed_products": self.allowed_products or [],
            "currency": self.currency,
            "offer_ttl_minutes": self.offer_ttl_minutes,
            "is_active": self.is_active,
        }
