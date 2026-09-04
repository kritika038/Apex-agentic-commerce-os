from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Numeric, Integer, ForeignKey, DateTime
from .base import TimeStampedBase, generate_uuid
from datetime import datetime, timezone
from typing import Optional

class TransactionAuthorization(TimeStampedBase):
    __tablename__ = "transaction_authorizations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    purchase_intent_id: Mapped[str] = mapped_column(ForeignKey("purchase_intents.id"), index=True)
    policy_evaluation_id: Mapped[str] = mapped_column(ForeignKey("policy_evaluations.id"), index=True)
    approval_request_id: Mapped[Optional[str]] = mapped_column(ForeignKey("approval_requests.id"), nullable=True, index=True)
    policy_version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String, default="AUTHORIZED", index=True) # AUTHORIZED, EXPIRED, REVOKED
    authorized_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String, default="INR")
    authorized_by: Mapped[str] = mapped_column(String) # POLICY_ENGINE_AUTO or user_id
    authorized_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)

    merchant = relationship("Merchant")
    purchase_intent = relationship("PurchaseIntent")
    policy_evaluation = relationship("PolicyEvaluation")
    approval_request = relationship("ApprovalRequest")
