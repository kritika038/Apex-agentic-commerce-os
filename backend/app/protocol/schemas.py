from pydantic import BaseModel, Field, ConfigDict
from decimal import Decimal
from typing import Optional, List, Dict, Any
from datetime import datetime

class ProtocolCapabilitiesResponse(BaseModel):
    protocol_version: str = "1.0.0"
    merchant_id: str
    merchant_name: str
    supported_currency: str = "INR"
    operations: List[str] = [
        "discover",
        "recommend",
        "purchase_intent",
        "authorization_lookup",
        "payment_request"
    ]
    capabilities: Dict[str, bool] = {
        "catalog_search": True,
        "inventory_validation": True,
        "authoritative_pricing": True,
        "contextual_recommendations": True,
        "structured_purchase_intents": True,
        "deterministic_policy_engine": True,
        "risk_scoring": True,
        "human_approval_workflow": True,
        "transaction_authorization": True,
        "payment_provider_abstraction": True,
        "cryptographic_audit_trail": True
    }
    security_guarantees: Dict[str, str] = {
        "price_authority": "DATABASE_GROUNDED",
        "inventory_authority": "DATABASE_GROUNDED",
        "payment_authority": "RESTRICTED_AUTHORIZATION_BOUNDARY",
        "audit_integrity": "SHA256_HASH_CHAINED",
        "tenant_isolation": "ENABLED"
    }

class ProtocolProductItem(BaseModel):
    id: str
    name: str
    category: str
    price: Decimal
    currency: str = "INR"
    in_stock: bool
    stock_quantity: int
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class ProtocolDiscoverRequest(BaseModel):
    query: Optional[str] = Field(None, description="Natural language search query or keyword")
    category: Optional[str] = Field(None, description="Category constraint")
    max_price: Optional[Decimal] = Field(None, description="Maximum budget limit")
    quantity: Optional[int] = Field(1, description="Quantity")
    currency: Optional[str] = Field("INR", description="Requested currency")
    preferences: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Buyer preference flags")
    session_id: Optional[str] = Field(None, description="Shopping session identifier")
    trace_id: Optional[str] = Field(None, description="End-to-end request trace ID")
    merchant_id: Optional[str] = Field(None, description="Target merchant ID")

class ProtocolDiscoverResponse(BaseModel):
    session_id: str
    trace_id: str
    products: List[ProtocolProductItem]
    total_found: int
    cart: List[Dict[str, Any]] = []
    message: Optional[str] = None

class ProtocolRecommendRequest(BaseModel):
    session_id: str = Field(..., description="Active session ID with cart context")
    buyer_preferences: Optional[Dict[str, Any]] = Field(default_factory=dict)
    trace_id: Optional[str] = Field(None, description="End-to-end request trace ID")
    merchant_id: Optional[str] = Field(None, description="Target merchant ID")

class ProtocolRecommendationItem(BaseModel):
    recommendation_id: str
    type: str # UPSELL, CROSS_SELL, BUNDLE
    recommended_product_id: str
    product_name: str
    product_price: Decimal
    currency: str = "INR"
    reason: str
    confidence: float
    status: str

    model_config = ConfigDict(from_attributes=True)

class ProtocolRecommendResponse(BaseModel):
    session_id: str
    trace_id: str
    recommendations: List[ProtocolRecommendationItem]

class ProtocolPurchaseIntentRequest(BaseModel):
    session_id: str = Field(..., description="Session ID containing authoritative cart items")
    buyer_id: str = Field(..., description="External AI buyer or customer identifier")
    constraints: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Optional buyer budget constraints")
    trace_id: Optional[str] = Field(None, description="End-to-end request trace ID")
    merchant_id: Optional[str] = Field(None, description="Target merchant ID")

class ProtocolPurchaseIntentResponse(BaseModel):
    purchase_intent_id: str
    merchant_id: str
    buyer_id: str
    cart_id: str
    status: str
    requested_amount: Decimal
    currency: str
    items: List[Dict[str, Any]]
    expires_at: datetime
    trace_id: str

    model_config = ConfigDict(from_attributes=True)

class ProtocolAuthorizationStatusResponse(BaseModel):
    purchase_intent_id: str
    merchant_id: str
    status: str # NOT_EVALUATED, AUTHORIZED, REQUIRES_APPROVAL, DENIED, EXPIRED
    authorization_id: Optional[str] = None
    authorized_amount: Optional[Decimal] = None
    currency: Optional[str] = None
    expires_at: Optional[datetime] = None
    risk_level: Optional[str] = None
    decision: Optional[str] = None
    approval_request_id: Optional[str] = None
    trace_id: Optional[str] = None

class ProtocolPaymentRequest(BaseModel):
    purchase_intent_id: str = Field(..., description="ID of the validated Purchase Intent")
    authorization_id: str = Field(..., description="ID of the valid Transaction Authorization")
    idempotency_key: str = Field(..., description="Client idempotency key to prevent double charges")
    trace_id: Optional[str] = Field(None, description="End-to-end request trace ID")
    merchant_id: Optional[str] = Field(None, description="Target merchant ID")

class ProtocolPaymentResponse(BaseModel):
    payment_transaction_id: str
    razorpay_order_id: Optional[str] = None
    amount: Decimal
    currency: str
    status: str
    receipt: str
    trace_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
