from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Index, JSON
from sqlalchemy.orm import relationship
from app.database.models.base import Base, generate_uuid

class AgentStep(Base):
    """
    Individual action step taken by an AI Agent (Tool execution, reasoning, recommendation).
    """
    __tablename__ = "agent_steps"

    id = Column(String, primary_key=True, default=generate_uuid)
    trace_id = Column(String, nullable=False, index=True)
    agent_trace_id = Column(String, ForeignKey("agent_traces.id"), nullable=False, index=True)
    sequence_number = Column(Integer, nullable=False)

    step_type = Column(String, nullable=False) # "TOOL_CALL", "REASONING", "RECOMMENDATION", "OUTPUT_GENERATION"
    tool_name = Column(String, nullable=True)

    input_schema = Column(JSON, nullable=True) # Redacted structured input
    input_hash = Column(String(64), nullable=True)
    output_schema = Column(JSON, nullable=True) # Redacted structured output
    output_hash = Column(String(64), nullable=True)

    decision = Column(String, nullable=True)
    duration_ms = Column(Float, nullable=False, default=0.0)
    status = Column(String, nullable=False, default="SUCCESS") # "SUCCESS", "FAILED", "DENIED"
    error_code = Column(String, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False, index=True)

    agent_trace = relationship("AgentTrace", back_populates="steps")

    __table_args__ = (
        Index("ix_agent_steps_trace_seq", "trace_id", "sequence_number"),
    )
