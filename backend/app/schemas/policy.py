from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime

class PolicyBase(BaseModel):
    name: str = Field(default="Default Commerce Policy", max_length=100)
    max_transaction_amount: Decimal = Field(default=Decimal("10000.00"), gt=0)
    approval_threshold: Decimal = Field(default=Decimal("5000.00"), ge=0)
    low_risk_limit: Decimal = Field(default=Decimal("2000.00"), ge=0)
    max_discount_percent: Decimal = Field(default=Decimal("5.00"), ge=0, le=100)
    max_quantity: int = Field(default=5, gt=0, le=100)
    allowed_currency: str = Field(default="INR", min_length=3, max_length=3)
    auto_approval_enabled: bool = True
    authorization_expiration_minutes: int = Field(default=10, gt=0, le=1440)

    model_config = ConfigDict(from_attributes=True)

class PolicyCreate(PolicyBase):
    pass

class PolicyUpdate(BaseModel):
    name: Optional[str] = None
    max_transaction_amount: Optional[Decimal] = Field(None, gt=0)
    approval_threshold: Optional[Decimal] = Field(None, ge=0)
    low_risk_limit: Optional[Decimal] = Field(None, ge=0)
    max_discount_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    max_quantity: Optional[int] = Field(None, gt=0, le=100)
    allowed_currency: Optional[str] = Field(None, min_length=3, max_length=3)
    auto_approval_enabled: Optional[bool] = None
    authorization_expiration_minutes: Optional[int] = Field(None, gt=0, le=1440)

    model_config = ConfigDict(from_attributes=True)

class PolicyResponse(PolicyBase):
    id: str
    merchant_id: str
    version: int
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class PolicyCheck(BaseModel):
    rule: str
    passed: bool
    details: Optional[str] = None

class PolicyEvaluationResponse(BaseModel):
    id: str
    merchant_id: str
    policy_id: str
    policy_version: int
    purchase_intent_id: str
    trace_id: Optional[str] = None
    decision: str # ALLOW, REQUIRES_APPROVAL, DENY
    risk_level: str # LOW, MEDIUM, HIGH
    requires_human_approval: bool
    checks: List[Dict[str, Any]] = []
    violations: List[str] = []
    policy_snapshot: Dict[str, Any] = {}
    evaluated_at: Optional[datetime] = None
    authorization: Optional[Dict[str, Any]] = None
    approval_request: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)

class ApprovalRequestResponse(BaseModel):
    id: str
    merchant_id: str
    purchase_intent_id: str
    policy_evaluation_id: str
    requested_by_agent_id: Optional[str] = None
    amount: Decimal
    currency: str
    risk_level: str
    status: str # PENDING, APPROVED, REJECTED, EXPIRED, CANCELLED
    reason: str
    approved_by_user_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class ApprovalActionRequest(BaseModel):
    reason: Optional[str] = None

class TransactionAuthorizationResponse(BaseModel):
    id: str
    merchant_id: str
    purchase_intent_id: str
    policy_evaluation_id: str
    approval_request_id: Optional[str] = None
    policy_version: int
    status: str # AUTHORIZED, EXPIRED, REVOKED
    authorized_amount: Decimal
    currency: str
    authorized_by: str
    authorized_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class AgentResponse(BaseModel):
    id: str
    merchant_id: str
    name: str
    type: str
    version: str
    model: str
    status: str
    permissions: List[str] = []

    model_config = ConfigDict(from_attributes=True)

class AgentFirewallRule(BaseModel):
    agent_id: str
    name: str
    type: str
    version: str
    status: str
    granted_permissions: List[str]
    forbidden_permissions: List[str]
    allowed_tools: List[str]
    isolation_level: str = "SANDBOXED_READ_COMMERCE"
    can_authorize_payments: bool = False
    can_modify_prices: bool = False
    can_override_policies: bool = False

class AgentFirewallResponse(BaseModel):
    merchant_id: str
    firewall_status: str = "ACTIVE"
    total_agents: int
    agents: List[AgentFirewallRule]
    global_security_invariants: List[str] = [
        "No autonomous agent possesses AUTHORIZE_TRANSACTION permission",
        "Price authority strictly derived from SQL database records",
        "Deterministic Policy Engine executes outside LLM context",
        "Payment orders require cryptographically unexpired TransactionAuthorization",
        "Audit trail backed by SHA-256 hash chaining"
    ]
