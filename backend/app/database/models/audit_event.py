from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Index, Text, JSON, UniqueConstraint
from app.database.models.base import Base, generate_uuid

class AuditEvent(Base):
    """
    Immutable, append-only, tamper-evident audit event log.
    Chained cryptographically via previous_event_hash and event_hash SHA-256 signatures.
    """
    __tablename__ = "audit_events"

    id = Column(String, primary_key=True, default=generate_uuid)
    merchant_id = Column(String, ForeignKey("merchants.id"), nullable=False, index=True)
    trace_id = Column(String, nullable=False, index=True)
    sequence_number = Column(Integer, nullable=False)

    # Correlation Identifiers
    session_id = Column(String, nullable=True, index=True)
    purchase_intent_id = Column(String, nullable=True, index=True)
    order_id = Column(String, nullable=True, index=True)
    payment_transaction_id = Column(String, nullable=True, index=True)
    payment_attempt_id = Column(String, nullable=True, index=True)
    authorization_id = Column(String, nullable=True, index=True)
    approval_request_id = Column(String, nullable=True, index=True)
    agent_id = Column(String, nullable=True, index=True)
    agent_version = Column(String, nullable=True)
    webhook_event_id = Column(String, nullable=True, index=True)
    reconciliation_attempt_id = Column(String, nullable=True, index=True)

    # Actor Model: USER, AGENT, SYSTEM, PROVIDER, WEBHOOK
    actor_type = Column(String, nullable=False)
    actor_id = Column(String, nullable=True)

    # Action & Event Classification
    action = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    tool_name = Column(String, nullable=True)
    resource_type = Column(String, nullable=True)
    resource_id = Column(String, nullable=True)

    # State & Policy Snapshot
    previous_state = Column(String, nullable=True)
    new_state = Column(String, nullable=True)
    policy_result = Column(String, nullable=True)
    risk_level = Column(String, nullable=True)
    decision = Column(String, nullable=True)

    # Outcome Status & Error Auditing
    status = Column(String, nullable=False) # "SUCCESS", "FAILED", "DENIED", "REJECTED", "TIMEOUT"
    error_code = Column(String, nullable=True)
    reason = Column(Text, nullable=True)

    # Redacted Metadata
    metadata_json = Column(JSON, nullable=False, default=dict)
    request_hash = Column(String, nullable=True)

    # Cryptographic Hash Chaining (SHA-256)
    previous_event_hash = Column(String(64), nullable=False)
    event_hash = Column(String(64), nullable=False)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("merchant_id", "trace_id", "sequence_number", name="uq_audit_events_merchant_trace_seq"),
        Index("ix_audit_events_merchant_trace", "merchant_id", "trace_id"),
        Index("ix_audit_events_trace_created", "trace_id", "created_at"),
    )
