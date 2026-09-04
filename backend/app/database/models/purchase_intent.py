from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Numeric, JSON, ForeignKey, DateTime
from .base import TimeStampedBase, generate_uuid
from datetime import datetime
from typing import Optional

class PurchaseIntent(TimeStampedBase):
    __tablename__ = "purchase_intents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    buyer_id: Mapped[str] = mapped_column(String, index=True)
    session_id: Mapped[str] = mapped_column(String, index=True)
    cart_id: Mapped[str] = mapped_column(ForeignKey("carts.id"), index=True)
    status: Mapped[str] = mapped_column(String, default="CREATED", index=True) # DRAFT, CREATED, VALIDATED, REJECTED, EXPIRED, CONVERTED
    currency: Mapped[str] = mapped_column(String, default="INR")
    requested_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    product_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    constraints: Mapped[dict] = mapped_column(JSON, default=dict)
    delivery_address: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    trace_id: Mapped[Optional[str]] = mapped_column(String, index=True, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True, nullable=True)

    cart = relationship("Cart")
    merchant = relationship("Merchant")
