from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime

class PaymentAttemptResponse(BaseModel):
    id: str
    merchant_id: str
    payment_transaction_id: str
    attempt_number: int
    provider: str
    operation: str
    idempotency_key: str
    status: str
    provider_order_id: Optional[str] = None
    provider_payment_id: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

class ReconciliationAttemptResponse(BaseModel):
    id: str
    merchant_id: str
    payment_transaction_id: str
    attempt_number: int
    previous_status: str
    provider_status: Optional[str] = None
    resolved_status: str
    reason: str
    started_at: datetime
    completed_at: datetime

    model_config = {"from_attributes": True}

class TimelineEventResponse(BaseModel):
    timestamp: datetime
    event_type: str
    title: str
    description: str
    badge_variant: str # "success" | "warning" | "error" | "info"
    metadata: Optional[dict] = None

class SimulatorScenarioRequest(BaseModel):
    scenario: str = Field(..., description="Simulation scenario: TIMEOUT, PROVIDER_4XX, SUCCESS, RECONCILIATION, INVALID_WEBHOOK_SIGNATURE, OUT_OF_ORDER_WEBHOOK")
    transaction_id: Optional[str] = None
    purchase_intent_id: Optional[str] = None
    authorization_id: Optional[str] = None

class SimulatorScenarioResponse(BaseModel):
    scenario: str
    status: Optional[str] = None
    payment_transaction_id: Optional[str] = None
    failure_code: Optional[str] = None
    failure_message: Optional[str] = None
    recovery_action: Optional[str] = None
    detail: Optional[str] = None
    downgrade_prevented: Optional[bool] = None
    message: Optional[str] = None
