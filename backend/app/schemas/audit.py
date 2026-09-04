from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime

class AuditEventResponse(BaseModel):
    id: str
    sequence_number: int
    merchant_id: str
    trace_id: str
    session_id: Optional[str] = None
    purchase_intent_id: Optional[str] = None
    order_id: Optional[str] = None
    payment_transaction_id: Optional[str] = None
    payment_attempt_id: Optional[str] = None
    authorization_id: Optional[str] = None
    approval_request_id: Optional[str] = None
    agent_id: Optional[str] = None
    agent_version: Optional[str] = None
    actor_type: str
    actor_id: Optional[str] = None
    action: str
    event_type: str
    tool_name: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    previous_state: Optional[str] = None
    new_state: Optional[str] = None
    policy_result: Optional[str] = None
    risk_level: Optional[str] = None
    decision: Optional[str] = None
    status: str
    error_code: Optional[str] = None
    reason: Optional[str] = None
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    previous_event_hash: str
    event_hash: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class AuditIntegrityStatus(BaseModel):
    is_valid: bool
    tampering_detected: bool
    detail: str

class TraceSummaryResponse(BaseModel):
    trace_id: str
    merchant_id: str
    event_count: int
    first_timestamp: Optional[str] = None
    last_timestamp: Optional[str] = None
    duration_ms: float = 0.0
    current_status: str
    final_outcome: str
    integrity: AuditIntegrityStatus
    agent_count: int = 0
    tool_call_count: int = 0
    policy_decision: Optional[str] = None
    risk_level: Optional[str] = None
    approval_status: Optional[str] = None
    payment_status: Optional[str] = None
    events: List[Dict[str, Any]] = []

    model_config = ConfigDict(from_attributes=True)

class PaginatedAuditEvents(BaseModel):
    items: List[AuditEventResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

class AgentStepResponse(BaseModel):
    id: str
    sequence_number: int
    step_type: str
    tool_name: Optional[str] = None
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    decision: Optional[str] = None
    duration_ms: float = 0.0
    status: str
    error_code: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class AgentTraceResponse(BaseModel):
    id: str
    trace_id: str
    merchant_id: str
    session_id: Optional[str] = None
    agent_id: str
    agent_type: str
    agent_version: str
    model: str
    provider: str
    status: str
    token_usage: int
    latency_ms: float
    tool_call_count: int
    error_code: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    steps: List[AgentStepResponse] = []

    model_config = ConfigDict(from_attributes=True)

class ObservabilityMetricsResponse(BaseModel):
    commerce: Dict[str, Any]
    policy: Dict[str, Any]
    approval: Dict[str, Any]
    payment: Dict[str, Any]
    agent: Dict[str, Any]
