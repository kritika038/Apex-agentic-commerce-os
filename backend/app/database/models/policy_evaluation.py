from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Boolean, JSON, ForeignKey, DateTime
from .base import TimeStampedBase, generate_uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

class PolicyEvaluation(TimeStampedBase):
    __tablename__ = "policy_evaluations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    policy_id: Mapped[str] = mapped_column(ForeignKey("policies.id"), index=True)
    policy_version: Mapped[int] = mapped_column(Integer, index=True)
    policy_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    purchase_intent_id: Mapped[str] = mapped_column(ForeignKey("purchase_intents.id"), index=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String, index=True, nullable=True)
    decision: Mapped[str] = mapped_column(String, index=True) # ALLOW, REQUIRES_APPROVAL, DENY
    risk_level: Mapped[str] = mapped_column(String, index=True) # LOW, MEDIUM, HIGH
    requires_human_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    checks: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    violations: Mapped[List[str]] = mapped_column(JSON, default=list)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    merchant = relationship("Merchant")
    policy = relationship("Policy")
    purchase_intent = relationship("PurchaseIntent")
