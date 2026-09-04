from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, JSON, ForeignKey, DateTime, Boolean
from .base import TimeStampedBase, generate_uuid
from datetime import datetime
from typing import Optional, Dict, Any

class SecurityAttackResult(TimeStampedBase):
    __tablename__ = "security_attack_results"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    scenario_id: Mapped[str] = mapped_column(String, index=True)
    scenario_name: Mapped[str] = mapped_column(String)
    request_payload_redacted: Mapped[dict] = mapped_column(JSON, default=dict)
    expected_result: Mapped[str] = mapped_column(String)
    actual_result: Mapped[str] = mapped_column(String)
    blocked: Mapped[bool] = mapped_column(Boolean, default=True)
    block_layer: Mapped[str] = mapped_column(String) # SCHEMA_VALIDATION, TENANT_ISOLATION, PERMISSION_FIREWALL, POLICY_ENGINE, AUTHORIZATION, PAYMENT_SERVICE, WEBHOOK_VERIFICATION, STATE_MACHINE, AUDIT_INTEGRITY
    reason: Mapped[str] = mapped_column(String)
    trace_id: Mapped[Optional[str]] = mapped_column(String, index=True, nullable=True)
    audit_event_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    merchant = relationship("Merchant")
