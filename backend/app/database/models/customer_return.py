from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Numeric, ForeignKey
from .base import TimeStampedBase, generate_uuid
from typing import Optional

class CustomerReturn(TimeStampedBase):
    """
    Persisted customer return requests with deterministic state management.
    """
    __tablename__ = "customer_returns"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    order_id: Mapped[str] = mapped_column(String, index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    reason: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="REQUESTED") # REQUESTED, APPROVED, REJECTED, COMPLETED
    refund_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    product = relationship("Product")
    user = relationship("User")
