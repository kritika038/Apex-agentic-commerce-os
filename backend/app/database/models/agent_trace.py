from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.database.models.base import Base, generate_uuid

class AgentTrace(Base):
    """
    Detailed execution trace of an AI Agent (ShoppingAgent, SalesAgent, BuyerAgent).
    Stores model metadata, performance metrics, and privacy-preserving hashes.
    """
    __tablename__ = "agent_traces"

    id = Column(String, primary_key=True, default=generate_uuid)
    trace_id = Column(String, nullable=False, index=True)
    merchant_id = Column(String, ForeignKey("merchants.id"), nullable=False, index=True)
    session_id = Column(String, nullable=True, index=True)

    agent_id = Column(String, nullable=False, index=True) # e.g. "shopping_agent_01"
    agent_type = Column(String, nullable=False) # "SHOPPING_AGENT", "SALES_AGENT", "BUYER_AGENT"
    agent_version = Column(String, nullable=False, default="1.0.0")

    model = Column(String, nullable=False, default="gemini-2.5-pro")
    provider = Column(String, nullable=False, default="google")

    status = Column(String, nullable=False, default="SUCCESS") # "STARTED", "SUCCESS", "FAILED"
    input_hash = Column(String(64), nullable=True)
    output_hash = Column(String(64), nullable=True)

    token_usage = Column(Integer, nullable=False, default=0)
    latency_ms = Column(Float, nullable=False, default=0.0)
    tool_call_count = Column(Integer, nullable=False, default=0)
    error_code = Column(String, nullable=True)

    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False, index=True)

    steps = relationship("AgentStep", back_populates="agent_trace", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_agent_traces_merchant_trace", "merchant_id", "trace_id"),
        Index("ix_agent_traces_agent_created", "agent_id", "created_at"),
    )
