from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class AgentShoppingSessionState(BaseModel):
    """
    Structured shopping agent session state persisted server-side across conversational turns.
    """
    intent: str = Field("IDLE", description="Active high-level conversation intent")
    category: Optional[str] = Field(None, description="Active product category filter")
    subcategory: Optional[str] = Field(None, description="Active product subcategory filter")
    brand_preference: Optional[str] = Field(None, description="Explicit brand requested by user")
    budget_max: Optional[float] = Field(None, description="Maximum budget in INR")
    budget_min: Optional[float] = Field(None, description="Minimum budget in INR")
    currency: str = Field("INR", description="Currency code")
    use_case: Optional[str] = Field(None, description="Specific use case (e.g. marathon, trail, daily, gym)")
    gender_if_explicit: Optional[str] = Field(None, description="Explicit gender constraint")
    size_if_explicit: Optional[str] = Field(None, description="Explicit size constraint (e.g. UK 8, M)")
    colour_if_explicit: Optional[str] = Field(None, description="Explicit colour constraint (e.g. Black, White)")
    quantity: int = Field(1, ge=1, le=10, description="Target item quantity")
    candidate_products: List[Dict[str, Any]] = Field(default_factory=list, description="Surviving candidate products")
    selected_product: Optional[Dict[str, Any]] = Field(None, description="Currently focused or selected product")
    selected_variant: Optional[Dict[str, Any]] = Field(None, description="Currently focused or selected variant")
    cart_items: List[Dict[str, Any]] = Field(default_factory=list, description="Authoritative cart item snapshots")
    coupon: Optional[str] = Field(None, description="Applied coupon code")
    reward_coins_used: bool = Field(False, description="Whether reward coins are redeemed")
    verified_price_observations: Dict[str, Any] = Field(default_factory=dict, description="Cached canonical price observations")
    checkout_state: str = Field("IDLE", description="IDLE | REVIEW | APPROVAL_REQUIRED | APPROVED | PAYMENT_PENDING | ORDER_CONFIRMED")
    governance_state: str = Field("AUTONOMOUS", description="AUTONOMOUS | APPROVAL_REQUIRED | POLICY_BLOCKED")
    purchase_intent_id: Optional[str] = Field(None, description="Associated Purchase Intent ID")
    correlation_id: str = Field("", description="Audit trace correlation ID")
    clarification_prompt: Optional[str] = Field(None, description="Active clarification prompt if intent was ambiguous")
