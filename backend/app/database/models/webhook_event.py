from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, DateTime, JSON, UniqueConstraint, Index
from .base import TimeStampedBase, generate_uuid
from datetime import datetime, timezone
from typing import Optional, Any

class WebhookEvent(TimeStampedBase):
    __tablename__ = "webhook_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    merchant_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    event_id: Mapped[str] = mapped_column(String, unique=True, index=True) # x-razorpay-event-id
    event_type: Mapped[str] = mapped_column(String, index=True) # payment.captured, payment.authorized, payment.failed, order.paid
    payload_hash: Mapped[str] = mapped_column(String)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    
    received_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Processing Status: RECEIVED, PROCESSED, DUPLICATE, FAILED, IGNORED
    processing_status: Mapped[str] = mapped_column(String, default="RECEIVED", index=True)
    error_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    __table_args__ = (
        UniqueConstraint("event_id", name="uq_webhook_event_id"),
        Index("ix_webhook_events_type_status", "event_type", "processing_status"),
    )
