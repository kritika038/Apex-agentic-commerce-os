from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime

class BuyerConstraints(BaseModel):
    max_price: Optional[Decimal] = Field(None, gt=0, description="Maximum total price requested by buyer")
    currency: str = Field("INR", min_length=3, max_length=3)
    quantity: int = Field(1, ge=1, le=100)
    category: Optional[str] = Field(None, max_length=100)
    preferences: List[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

class BuyerRequest(BaseModel):
    buyer_id: str = Field(..., min_length=1, max_length=100)
    session_id: str = Field(..., min_length=1, max_length=100)
    merchant_id: Optional[str] = Field(None, max_length=100)
    message: str = Field(..., min_length=1, max_length=1000)
    constraints: Optional[BuyerConstraints] = None

    model_config = ConfigDict(from_attributes=True)

class DeliveryAddress(BaseModel):
    full_name: str = Field(..., description="Customer full name")
    phone: str = Field(..., description="10-digit Indian mobile number")
    email: str = Field(..., description="Customer email address")
    address_line1: str = Field(..., description="House / Flat / Street")
    address_line2: Optional[str] = Field(None, description="Apartment / Area")
    landmark: Optional[str] = Field(None, description="Nearby landmark")
    city: str = Field(..., description="City")
    state: str = Field(..., description="State / Union Territory")
    pin_code: str = Field(..., description="6-digit PIN code")
    country: str = Field("India", description="Country")

    model_config = ConfigDict(from_attributes=True)

class PurchaseIntentCreate(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=100)
    buyer_id: str = Field(..., min_length=1, max_length=100)
    merchant_id: Optional[str] = Field(None, max_length=100)
    delivery_address: Optional[DeliveryAddress] = None
    constraints: Optional[BuyerConstraints] = None
    coupon_code: Optional[str] = None
    voucher_code: Optional[str] = None
    use_coins: bool = False
    coins_to_redeem: Optional[int] = None
    trace_id: Optional[str] = Field(None, max_length=100)

class PurchaseIntentItem(BaseModel):
    product_id: str
    name: str
    quantity: int
    unit_price: Decimal
    subtotal: Decimal

    model_config = ConfigDict(from_attributes=True)

class PurchaseIntentResponse(BaseModel):
    id: str
    status: str
    merchant_id: str
    buyer_id: str
    cart_id: str
    currency: str
    requested_amount: Decimal
    items: List[PurchaseIntentItem] = []
    delivery_address: Optional[Dict[str, Any]] = None
    constraints: Dict[str, Any] = Field(default_factory=dict)
    trace_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class RecommendationResponse(BaseModel):
    id: str
    type: str # UPSELL, CROSS_SELL, BUNDLE
    recommended_product_id: str
    product_name: str
    product_price: Decimal
    reason: str
    confidence: float
    status: str # GENERATED, SHOWN, ACCEPTED, REJECTED, EXPIRED
    source_product_id: Optional[str] = None
    trace_id: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class RecommendationStatsResponse(BaseModel):
    total_recommendations: int
    accepted_count: int
    rejected_count: int
    acceptance_rate: float # percentage, e.g. 28.5
    additional_cart_value: Decimal # sum of value added by accepted recommendations
    recent_recommendations: List[RecommendationResponse] = []

    model_config = ConfigDict(from_attributes=True)
