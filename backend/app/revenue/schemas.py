from pydantic import BaseModel, Field, ConfigDict
from decimal import Decimal
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

class HumanView(BaseModel):
    title: str
    headline: str
    why_bullets: List[str] = []
    recommended_action: str
    financial_impact: str
    policy_badge: str # PASS, REQUIRES_APPROVAL, POLICY_BLOCKED, INSUFFICIENT_DATA, INVENTORY_RISK, EXPIRED
    governance_detail: str

class AgentView(BaseModel):
    opportunity_id: str
    merchant_id: str
    type: str # CROSS_SELL, UPSELL, BUNDLE, CONVERSION_IMPROVEMENT, PRICE_COMPETITIVENESS, INVENTORY_OPPORTUNITY
    source_product_id: Optional[str] = None
    target_product_ids: List[str] = []
    confidence: Optional[float] = None
    confidence_status: str = "CONFIDENT" # CONFIDENT, INSUFFICIENT_DATA
    estimated_incremental_gmv: Optional[Decimal] = None
    proposed_discount_percent: Decimal = Decimal("5.00")
    evidence: Dict[str, Any] = {}
    policy_status: str = "PASS" # PASS, REQUIRES_APPROVAL, POLICY_BLOCKED, INSUFFICIENT_DATA, INVENTORY_RISK, EXPIRED
    approval_required: bool = True
    can_execute: bool = False
    expires_at: Optional[datetime] = None
    calculation_method: Optional[str] = None
    data_window: Optional[str] = "last_30_days"

class RevenueOpportunityResponse(BaseModel):
    id: str
    merchant_id: str
    type: str # CROSS_SELL, UPSELL, BUNDLE, CAMPAIGN, INVENTORY_RISK, PRICE_COMPETITIVENESS
    source_product_id: Optional[str] = None
    target_product_ids: List[str] = []
    title: str
    description: str
    reason: str
    confidence: Optional[float] = None
    proposed_discount_percent: Decimal = Decimal("5.00")
    estimated_conversion_rate: float = 0.08
    estimated_incremental_orders: int = 10
    estimated_incremental_gmv: Optional[Decimal] = None
    estimated_discount_cost: Optional[Decimal] = None
    estimated_net_value: Optional[Decimal] = None
    inventory_impact: Dict[str, Any] = {}
    evidence_json: Dict[str, Any] = {}
    calculation_method: Optional[str] = None
    data_window: Optional[str] = "last_30_days"
    expires_at: Optional[datetime] = None
    idempotency_key: Optional[str] = None
    risk_level: str = "LOW"
    status: str = "GENERATED"
    simulation_payload: Dict[str, Any] = {}
    approved_by_user_id: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    trace_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    human_view: Optional[HumanView] = None
    agent_view: Optional[AgentView] = None

    model_config = ConfigDict(from_attributes=True)

class RevenueOpportunityGenerateRequest(BaseModel):
    types: Optional[List[str]] = Field(default=None, description="Optional filter for CROSS_SELL, UPSELL, BUNDLE, CAMPAIGN, INVENTORY_OPPORTUNITY")
    min_confidence: Optional[float] = Field(default=0.70, ge=0.0, le=1.0)
    trace_id: Optional[str] = None
    merchant_id: Optional[str] = None

class RevenueSimulationRequest(BaseModel):
    opportunity_id: str
    discount_percent: Optional[Decimal] = Field(default=None, ge=0, le=100)
    target_orders: Optional[int] = Field(default=None, ge=1, le=1000)
    trace_id: Optional[str] = None
    merchant_id: Optional[str] = None

class RevenueSimulationResponse(BaseModel):
    opportunity_id: str
    baseline_gmv: Decimal
    projected_orders: int
    projected_gmv: Decimal
    discount_cost: Decimal
    incremental_gmv: Decimal
    net_incremental_value: Decimal
    inventory_consumption: Dict[str, int]
    policy_compliant: bool
    policy_check_details: str
    risk_level: str
    is_simulated: bool = True
    simulation_label: str = "SIMULATED — NOT ACTUAL REVENUE"
    calculated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

class RevenueOpportunityApproveRequest(BaseModel):
    reason: Optional[str] = Field(default="Merchant operator approved revenue campaign")

class RevenueOpportunityRejectRequest(BaseModel):
    reason: str = Field(..., min_length=3, description="Mandatory reason for rejecting revenue proposal")

class RevenueOpportunityExecuteRequest(BaseModel):
    idempotency_key: str = Field(..., min_length=8, description="Client idempotency key preventing duplicate campaign executions")
    trace_id: Optional[str] = None
    merchant_id: Optional[str] = None

class RevenueMetricsResponse(BaseModel):
    total_opportunities: int
    projected_incremental_gmv: Optional[Decimal] = None
    actual_incremental_gmv: Decimal = Decimal("0.00")
    approval_rate: float
    executed_campaigns: int
    policy_blocks: int
    measurement_status: str = "SIMULATION_BENCHMARK_ACTIVE"
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

class RevenueExperimentItem(BaseModel):
    opportunity_id: str
    title: str
    type: str
    status: str
    simulated_net_value: Decimal
    actual_orders: int
    actual_gmv: Decimal
    executed_at: Optional[datetime] = None
    measurement_status: str = "SIMULATED"

class MerchantAgentQueryRequest(BaseModel):
    message: str = Field(..., min_length=2, description="Natural language inquiry from merchant")
    merchant_id: Optional[str] = None
    trace_id: Optional[str] = None

class MerchantAgentQueryResponse(BaseModel):
    query: str
    summary_message: str
    intent_detected: str
    total_opportunities_found: int
    opportunities: List[RevenueOpportunityResponse] = []
    top_human_view: Optional[HumanView] = None
    top_agent_view: Optional[AgentView] = None
    trace_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
