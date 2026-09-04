from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Numeric, JSON, ForeignKey, DateTime, Float, Integer
from .base import TimeStampedBase, generate_uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

class RevenueOpportunity(TimeStampedBase):
    __tablename__ = "revenue_opportunities"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    type: Mapped[str] = mapped_column(String, index=True) # CROSS_SELL, UPSELL, BUNDLE, CAMPAIGN
    source_product_id: Mapped[Optional[str]] = mapped_column(ForeignKey("products.id"), nullable=True)
    target_product_ids: Mapped[list] = mapped_column(JSON, default=list)
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String)
    reason: Mapped[str] = mapped_column(String)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Deterministic Simulation Estimates
    proposed_discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("5.00"))
    estimated_conversion_rate: Mapped[float] = mapped_column(Float, default=0.08)
    estimated_incremental_orders: Mapped[int] = mapped_column(Integer, default=10)
    estimated_incremental_gmv: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    estimated_discount_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    estimated_net_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    inventory_impact: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Evidence & Expiration
    evidence_json: Mapped[dict] = mapped_column(JSON, default=dict)
    calculation_method: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    data_window: Mapped[Optional[str]] = mapped_column(String, default="last_30_days", nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String, index=True, nullable=True)
    
    risk_level: Mapped[str] = mapped_column(String, default="LOW") # LOW, MEDIUM, HIGH, INSUFFICIENT_DATA, INVENTORY_RISK
    status: Mapped[str] = mapped_column(String, default="GENERATED", index=True) # GENERATED, SIMULATED, PENDING_APPROVAL, APPROVED, REJECTED, EXECUTED, EXPIRED, CANCELLED, POLICY_BLOCKED
    simulation_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Audit & Approval
    approved_by_user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    rejected_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String, index=True, nullable=True)

    merchant = relationship("Merchant")
    source_product = relationship("Product", foreign_keys=[source_product_id])
