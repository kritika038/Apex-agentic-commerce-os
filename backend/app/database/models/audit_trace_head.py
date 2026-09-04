from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, UniqueConstraint, Index
from app.database.models.base import Base, generate_uuid

class AuditTraceHead(Base):
    """
    Tracks the active tail/tip of each trace's hash chain to guarantee serialized,
    fork-free concurrent event insertions.
    """
    __tablename__ = "audit_trace_heads"

    id = Column(String, primary_key=True, default=generate_uuid)
    merchant_id = Column(String, ForeignKey("merchants.id"), nullable=False, index=True)
    trace_id = Column(String, nullable=False, index=True)
    
    latest_sequence_number = Column(Integer, nullable=False, default=0)
    latest_event_id = Column(String, nullable=True)
    latest_event_hash = Column(String(64), nullable=False) # "0"*64 on init
    
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False)

    __table_args__ = (
        UniqueConstraint("merchant_id", "trace_id", name="uq_audit_trace_head_merchant_trace"),
        Index("ix_trace_head_merchant_trace", "merchant_id", "trace_id"),
    )
