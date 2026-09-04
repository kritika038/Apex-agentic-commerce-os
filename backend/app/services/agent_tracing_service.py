import hashlib
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.database.models.agent_trace import AgentTrace
from app.database.models.agent_step import AgentStep
from app.utils.redaction import redact_sensitive_data

class AgentTracingService:
    """
    Tracing and metrics collection service for AI Agents.
    Records agent executions, token usage, tool interactions, and privacy-preserving hashes.
    """

    @staticmethod
    def _compute_hash(data: Any) -> Optional[str]:
        if data is None:
            return None
        sanitized = redact_sensitive_data(data)
        encoded = json.dumps(sanitized, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def start_agent_trace(
        db: Session,
        trace_id: str,
        merchant_id: str,
        agent_id: str,
        agent_type: str,
        agent_version: str = "1.0.0",
        session_id: Optional[str] = None,
        model: str = "gemini-2.5-pro",
        provider: str = "google",
        input_data: Optional[Any] = None
    ) -> AgentTrace:
        trace = AgentTrace(
            trace_id=trace_id,
            merchant_id=merchant_id,
            session_id=session_id,
            agent_id=agent_id,
            agent_type=agent_type,
            agent_version=agent_version,
            model=model,
            provider=provider,
            status="STARTED",
            input_hash=AgentTracingService._compute_hash(input_data),
            started_at=datetime.now(timezone.utc).replace(tzinfo=None)
        )
        db.add(trace)
        db.flush()
        return trace

    @staticmethod
    def record_step(
        db: Session,
        trace_id: str,
        agent_trace_id: str,
        sequence_number: int,
        step_type: str,
        tool_name: Optional[str] = None,
        input_data: Optional[Any] = None,
        output_data: Optional[Any] = None,
        decision: Optional[str] = None,
        duration_ms: float = 0.0,
        status: str = "SUCCESS",
        error_code: Optional[str] = None
    ) -> AgentStep:
        sanitized_input = redact_sensitive_data(input_data) if input_data else None
        sanitized_output = redact_sensitive_data(output_data) if output_data else None

        step = AgentStep(
            trace_id=trace_id,
            agent_trace_id=agent_trace_id,
            sequence_number=sequence_number,
            step_type=step_type,
            tool_name=tool_name,
            input_schema=sanitized_input,
            input_hash=AgentTracingService._compute_hash(sanitized_input),
            output_schema=sanitized_output,
            output_hash=AgentTracingService._compute_hash(sanitized_output),
            decision=decision,
            duration_ms=duration_ms,
            status=status,
            error_code=error_code
        )
        db.add(step)
        db.flush()
        return step

    @staticmethod
    def complete_agent_trace(
        db: Session,
        agent_trace_id: str,
        status: str = "SUCCESS",
        output_data: Optional[Any] = None,
        token_usage: int = 0,
        tool_call_count: int = 0,
        error_code: Optional[str] = None
    ) -> AgentTrace:
        trace = db.query(AgentTrace).filter(AgentTrace.id == agent_trace_id).first()
        if not trace:
            return None

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        latency = (now - trace.started_at).total_seconds() * 1000.0

        trace.status = status
        trace.output_hash = AgentTracingService._compute_hash(output_data)
        trace.token_usage = token_usage
        trace.tool_call_count = tool_call_count
        trace.latency_ms = latency
        trace.completed_at = now
        trace.error_code = error_code

        db.flush()
        return trace
