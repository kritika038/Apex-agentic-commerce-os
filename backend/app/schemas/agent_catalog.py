"""
Pydantic schemas for the Agent-Readable Catalog & AI Buyer Agent API.
Follows strict machine-readable, transaction-ready contracts.
"""

from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime

class AgentVariantItem(BaseModel):
    variant_id: str
    display_name: str
    color: Optional[str] = None
    size: Optional[str] = None
    style_code: Optional[str] = None
    gtin: Optional[str] = None
    price: float
    mrp: Optional[float] = None
    currency: str = "INR"
    availability: str = "in_stock"
    inventory_available: bool = True
    stock_quantity: int = 10
    garment_asset: Optional[str] = None
    vto_eligible: bool = False

class AgentProductDetail(BaseModel):
    product_id: str
    merchant_id: str
    name: str
    description: Optional[str] = None
    brand: str
    category: str
    subcategory: Optional[str] = None
    currency: str = "INR"
    price: float
    mrp: Optional[float] = None
    availability: str = "in_stock"
    inventory_available: bool = True
    stock_quantity: int
    variants: List[AgentVariantItem] = []
    attributes: Dict[str, Any] = {}
    agent_buyable: bool = True
    agent_buyability_reason: Optional[str] = None
    purchase_constraints: Dict[str, Any] = {
        "max_order_quantity": 5,
        "requires_approval_above": 5000.0,
        "allowed_currency": "INR"
    }
    canonical_identity: Dict[str, Any] = {}
    image_url: Optional[str] = None

class AgentCatalogResponse(BaseModel):
    total: int
    skip: int
    limit: int
    currency: str = "INR"
    generated_at: str
    products: List[AgentProductDetail]

class AgentSearchRequest(BaseModel):
    query: Optional[str] = None
    budget_max: Optional[float] = None
    min_price: Optional[float] = None
    brand: Optional[Union[List[str], str]] = None
    category: Optional[str] = None
    color: Optional[str] = None
    size: Optional[str] = None
    availability: Optional[str] = None # in_stock / all
    merchant_id: Optional[str] = None
    sort: Optional[str] = None # price_asc, price_desc, rating_desc, relevance
    limit: int = Field(20, ge=1, le=100)
    skip: int = Field(0, ge=0)

class AgentSearchResponse(BaseModel):
    results: List[AgentProductDetail]
    total: int
    applied_filters: Dict[str, Any]
    search_id: str
    generated_at: str

class AgentAvailabilityResponse(BaseModel):
    product_id: str
    is_active: bool
    in_stock: bool
    stock_quantity: int
    availability: str
    agent_buyable: bool
    agent_buyability_reason: Optional[str] = None
    variants_availability: List[Dict[str, Any]] = []
    checked_at: str

class AgentToolParameterProperty(BaseModel):
    type: str
    description: Optional[str] = None
    enum: Optional[List[str]] = None

class AgentToolDefinition(BaseModel):
    name: str
    description: str
    side_effect: bool = False
    authorization_requirement: str = "PUBLIC"
    parameters: Dict[str, Any]
    output_schema: Optional[Dict[str, Any]] = None

class AgentPurchaseIntentCreate(BaseModel):
    product_id: str
    variant_id: Optional[str] = None
    quantity: int = Field(1, ge=1, le=10)
    delivery_address: Optional[Dict[str, Any]] = None
    idempotency_key: Optional[str] = None
    coupon_code: Optional[str] = None
    use_coins: bool = False

class AgentPurchaseIntentDetail(BaseModel):
    purchase_intent_id: str
    status: str
    buyer_id: str
    merchant_id: str
    product_id: str
    product_name: str
    variant_id: Optional[str] = None
    quantity: int
    authoritative_unit_price: float
    total_amount: float
    discount_amount: float = 0.0
    currency: str = "INR"
    governance_decision: str
    requires_human_approval: bool
    trace_id: str
    created_at: str
    expires_at: Optional[str] = None
    order_review: Dict[str, Any]
    message: str

class AgentBuyerActRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    delivery_address: Optional[Dict[str, Any]] = None
    coupon_code: Optional[str] = None
    use_coins: bool = False

class AgentBuyerActResponse(BaseModel):
    session_id: str
    trace_id: str
    reply_message: str
    intent: Dict[str, Any]
    tool_calls: List[Dict[str, Any]] = []
    candidate_products: List[AgentProductDetail] = []
    selected_product: Optional[AgentProductDetail] = None
    purchase_intent: Optional[AgentPurchaseIntentDetail] = None
    order_review: Optional[Dict[str, Any]] = None
    governance: Optional[Dict[str, Any]] = None
    next_action: str # "DISCOVERY" | "SELECTION" | "CONFIRMATION" | "PAYMENT_READY" | "BLOCKED"
    agent_view: Dict[str, Any]
