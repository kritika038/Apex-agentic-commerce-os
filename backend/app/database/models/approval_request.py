from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Numeric, ForeignKey, DateTime
from .base import TimeStampedBase, generate_uuid
from datetime import datetime
from typing import Optional

class ApprovalRequest(TimeStampedBase):
    __tablename__ = "approval_requests"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    purchase_intent_id: Mapped[str] = mapped_column(ForeignKey("purchase_intents.id"), index=True)
    policy_evaluation_id: Mapped[str] = mapped_column(ForeignKey("policy_evaluations.id"), index=True)
    requested_by_agent_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String, default="INR")
    risk_level: Mapped[str] = mapped_column(String, default="HIGH", index=True)
    status: Mapped[str] = mapped_column(String, default="PENDING", index=True) # PENDING, APPROVED, REJECTED, EXPIRED, CANCELLED
    reason: Mapped[str] = mapped_column(String)
    approved_by_user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True, nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    rejected_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    merchant = relationship("Merchant")
    purchase_intent = relationship("PurchaseIntent")
    policy_evaluation = relationship("PolicyEvaluation")
    approved_by = relationship("User")
