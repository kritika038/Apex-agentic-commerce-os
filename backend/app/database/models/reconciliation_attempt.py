from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Index, Text
from app.database.models.base import Base, generate_uuid

class ReconciliationAttempt(Base):
    """
    Immutable audit record of every reconciliation operation and outcome.
    """
    __tablename__ = "reconciliation_attempts"

    id = Column(String, primary_key=True, default=generate_uuid)
    merchant_id = Column(String, ForeignKey("merchants.id"), nullable=False, index=True)
    payment_transaction_id = Column(String, ForeignKey("payment_transactions.id"), nullable=False, index=True)
    
    attempt_number = Column(Integer, nullable=False, default=1)
    previous_status = Column(String, nullable=False) # e.g. "UNKNOWN", "ORDER_CREATED"
    provider_status = Column(String, nullable=True) # e.g. "paid", "created", "not_found"
    resolved_status = Column(String, nullable=False) # e.g. "CAPTURED", "FAILED", "ORDER_CREATED", "UNKNOWN"
    
    reason = Column(Text, nullable=False)
    provider_response_hash = Column(String, nullable=True) # SHA-256 hash of provider response
    
    trace_id = Column(String, nullable=True, index=True)
    
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False)
    completed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False)

    __table_args__ = (
        Index("ix_recon_attempts_tx_num", "payment_transaction_id", "attempt_number"),
    )
