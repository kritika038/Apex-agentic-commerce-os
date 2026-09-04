from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime

class AttackScenarioDefinition(BaseModel):
    scenario_id: str
    name: str
    category: str # FINANCIAL_INTEGRITY, POLICY_BYPASS, PERMISSIONS, MULTI_TENANT, CRYPTOGRAPHY, ADVERSARIAL_PROMPT
    description: str
    adversarial_payload: Dict[str, Any]
    expected_defense_layer: str

class SecurityAttackExecutionResponse(BaseModel):
    id: str
    scenario_id: str
    scenario_name: str
    attempted_payload: Dict[str, Any] = {}
    expected_result: str
    actual_result: str
    blocked: bool
    block_layer: str
    reason: str
    trace_id: Optional[str] = None
    executed_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(from_attributes=True)

class SecurityLabSummaryResponse(BaseModel):
    system_security_score: float = Field(..., description="Deterministic test pass percentage (0-100)")
    total_attacks: int
    blocked_attacks: int
    idempotent_attacks: int
    security_failures: int
    status_label: str = "INTERNAL_SECURITY_VERIFICATION_PASS"
    layer_breakdown: Dict[str, str] = {}
    results: List[SecurityAttackExecutionResponse] = []
