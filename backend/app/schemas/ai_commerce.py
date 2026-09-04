from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class AgentBuyerInfo(BaseModel):
    agent_id: str
    name: str = "Customer Shopping Agent"
    type: str = "customer_ai"
    owner_id: Optional[str] = None

class AgentMerchantInfo(BaseModel):
    merchant_id: str
    name: str = "Apex Sports"

class AgentSearchQuery(BaseModel):
    category: Optional[str] = None
    use_case: Optional[str] = None
    budget: Optional[float] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    quantity: int = 1
    currency: str = "INR"
    preferred_attributes: Optional[Dict[str, Any]] = None
    language: str = "english"

class AgentSearchRequest(BaseModel):
    protocol_version: str = "1.0"
    request_id: str
    session_id: Optional[str] = None
    buyer_agent: Optional[AgentBuyerInfo] = None
    natural_language_query: Optional[str] = None
    query: Optional[AgentSearchQuery] = None

class AgentProductOffer(BaseModel):
    offer_id: str
    product_id: str
    name: str
    category: str
    unit_price: float
    currency: str = "INR"
    availability: str
    stock_quantity: int
    quantity_available: bool
    description: Optional[str] = None
    image_url: Optional[str] = None
    merchant_id: str
    suitability_reason: Optional[str] = None
    timestamp: str

class AgentSearchResponse(BaseModel):
    protocol_version: str = "1.0"
    request_id: str
    status: str
    merchant: AgentMerchantInfo
    offers: List[AgentProductOffer] = []
    total_offers: int = 0
    explanation: str
    closest_alternative: Optional[AgentProductOffer] = None
    session_id: str
    trace_id: str

class AgentNegotiateRequest(BaseModel):
    protocol_version: str = "1.0"
    request_id: str
    session_id: str
    action: str
    new_budget: Optional[float] = None
    limit: Optional[int] = None
    natural_language_message: Optional[str] = None

class AgentSelectOfferRequest(BaseModel):
    protocol_version: str = "1.0"
    request_id: str
    session_id: str
    offer_id: Optional[str] = None
    product_id: Optional[str] = None
    selection_strategy: Optional[str] = "best_match"
    quantity: int = 1

class AgentSelectOfferResponse(BaseModel):
    protocol_version: str = "1.0"
    request_id: str
    session_id: str
    status: str
    selected_offer: Optional[AgentProductOffer] = None
    explanation: str
    recovery: Optional[Dict[str, Any]] = None

class AgentPurchaseIntentRequest(BaseModel):
    protocol_version: str = "1.0"
    request_id: str
    session_id: str
    offer_id: Optional[str] = None
    product_id: Optional[str] = None
    quantity: int = 1
    max_budget: Optional[float] = None
    coupon_code: Optional[str] = None
    use_coins: bool = False
    delivery_address: Optional[Dict[str, Any]] = None
    idempotency_key: Optional[str] = None

class AgentPurchaseIntentResponse(BaseModel):
    protocol_version: str = "1.0"
    request_id: str
    session_id: str
    purchase_intent_id: str
    status: str
    order_review: Dict[str, Any]
    requires_human_approval: bool
    approval_details: Optional[Dict[str, Any]] = None
    explanation: str
    trace_id: str

class AgentApprovePayRequest(BaseModel):
    protocol_version: str = "1.0"
    request_id: str
    purchase_intent_id: str
    approval_id: Optional[str] = None
    idempotency_key: str

class AgentApprovePayResponse(BaseModel):
    protocol_version: str = "1.0"
    request_id: str
    status: str
    purchase_intent_id: str
    authorization_id: str
    razorpay_order_id: str
    amount: float
    currency: str = "INR"
    key_id: Optional[str] = None
    razorpay_key_id: Optional[str] = None

class AgentVerifyPaymentRequest(BaseModel):
    protocol_version: str = "1.0"
    request_id: str
    purchase_intent_id: str
    authorization_id: str
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str

class AgentVerifyPaymentResponse(BaseModel):
    protocol_version: str = "1.0"
    request_id: str
    status: str
    order_id: Optional[str] = None
    order_number: Optional[str] = None
    total_paid: float
    currency: str = "INR"
    points_earned: int = 0
    audit_correlation_id: str
    message: str

class AICommerceActivityResponse(BaseModel):
    active_agent_requests: int
    today_shopping_requests: int
    products_discovered: int
    purchase_intents_count: int
    completed_orders_count: int
    total_ai_revenue: float
    recent_events: List[Dict[str, Any]]
