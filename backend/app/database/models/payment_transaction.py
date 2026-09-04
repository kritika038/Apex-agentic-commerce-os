from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Numeric, Integer, ForeignKey, DateTime, UniqueConstraint, Index
from .base import TimeStampedBase, generate_uuid
from datetime import datetime, timezone
from typing import Optional

class PaymentTransaction(TimeStampedBase):
    __tablename__ = "payment_transactions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    purchase_intent_id: Mapped[str] = mapped_column(ForeignKey("purchase_intents.id"), index=True)
    authorization_id: Mapped[str] = mapped_column(ForeignKey("transaction_authorizations.id"), index=True)
    
    razorpay_order_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    razorpay_payment_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String, default="INR")
    
    # State Machine: CREATED, ORDER_CREATING, ORDER_CREATED, PAYMENT_PENDING, AUTHORIZED, CAPTURED, FAILED, UNKNOWN, RECONCILING, CANCELLED
    status: Mapped[str] = mapped_column(String, default="CREATED", index=True)
    
    idempotency_key: Mapped[str] = mapped_column(String, index=True)
    receipt: Mapped[str] = mapped_column(String)
    attempt_count: Mapped[int] = mapped_column(Integer, default=1)
    
    failure_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    failure_message: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    authorized_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    captured_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    failed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    merchant = relationship("Merchant")
    purchase_intent = relationship("PurchaseIntent")
    authorization = relationship("TransactionAuthorization")

    __table_args__ = (
        UniqueConstraint("merchant_id", "idempotency_key", name="uq_payment_merchant_idempotency"),
        Index("ix_payment_transactions_merchant_status", "merchant_id", "status"),
        Index("ix_payment_transactions_created_at", "created_at"),
    )
