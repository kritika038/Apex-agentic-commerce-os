from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Index, Text
from sqlalchemy.orm import relationship
from app.database.models.base import Base, generate_uuid

class PaymentAttempt(Base):
    """
    Immutable audit record of every individual outbound provider interaction (order creation, fetch, capture).
    """
    __tablename__ = "payment_attempts"

    id = Column(String, primary_key=True, default=generate_uuid)
    merchant_id = Column(String, ForeignKey("merchants.id"), nullable=False, index=True)
    payment_transaction_id = Column(String, ForeignKey("payment_transactions.id"), nullable=False, index=True)
    
    attempt_number = Column(Integer, nullable=False, default=1)
    provider = Column(String, nullable=False) # "mock" | "razorpay"
    operation = Column(String, nullable=False) # "CREATE_ORDER" | "FETCH_ORDER" | "FETCH_PAYMENT" | "WEBHOOK_CAPTURE"
    
    idempotency_key = Column(String, nullable=False, index=True)
    request_fingerprint = Column(String, nullable=True) # SHA-256 hash of payload
    status = Column(String, nullable=False) # "STARTED" | "SUCCESS" | "TIMEOUT" | "CONNECTION_ERROR" | "PROVIDER_4XX" | "PROVIDER_5XX" | "FAILED"
    
    provider_order_id = Column(String, nullable=True, index=True)
    provider_payment_id = Column(String, nullable=True, index=True)
    
    error_code = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    
    trace_id = Column(String, nullable=True, index=True)
    
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False)
    completed_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False)

    __table_args__ = (
        Index("ix_payment_attempts_tx_num", "payment_transaction_id", "attempt_number"),
    )
