from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.schemas.commerce import DeliveryAddress

class OrderItem(BaseModel):
    product_id: str
    name: str
    category: Optional[str] = "Gear"
    quantity: int
    unit_price: Decimal
    subtotal: Decimal
    image_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class OrderPaymentInfo(BaseModel):
    method: str = "Razorpay"
    status: str
    razorpay_order_id: Optional[str] = None
    razorpay_payment_id: Optional[str] = None
    paid_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class OrderPriceSummary(BaseModel):
    subtotal: Decimal
    coupon_code: Optional[str] = None
    coupon_discount: Decimal = Decimal("0.00")
    voucher_code: Optional[str] = None
    voucher_discount: Decimal = Decimal("0.00")
    coins_used: int = 0
    coin_discount: Decimal = Decimal("0.00")
    delivery_charges: Decimal = Decimal("0.00")
    taxes: Decimal = Decimal("0.00")
    discount: Decimal = Decimal("0.00")
    total_amount: Decimal
    currency: str = "INR"
    points_earned: int = 0

    model_config = ConfigDict(from_attributes=True)

class OrderTimelineStep(BaseModel):
    title: str
    status: str # "COMPLETED", "CURRENT", "PENDING", "UNAVAILABLE"
    timestamp: Optional[datetime] = None
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class OrderResponse(BaseModel):
    id: str
    order_number: str
    purchase_intent_id: str
    created_at: datetime
    status: str # "CONFIRMED", "PROCESSING", "FAILED", "CANCELLED"
    total_amount: Decimal
    currency: str = "INR"
    items: List[OrderItem] = []
    payment: OrderPaymentInfo
    price_summary: OrderPriceSummary
    delivery_address: Optional[DeliveryAddress] = None
    timeline: List[OrderTimelineStep] = []

    model_config = ConfigDict(from_attributes=True)

class BuyAgainRequest(BaseModel):
    session_id: str = Field(..., description="Target cart session to add items to")

    model_config = ConfigDict(from_attributes=True)

class BuyAgainResponse(BaseModel):
    success: bool
    added_items: List[Dict[str, Any]]
    unavailable_items: List[Dict[str, Any]]
    cart: Dict[str, Any]
    message: str

    model_config = ConfigDict(from_attributes=True)

class OrderCancelRequest(BaseModel):
    reason: Optional[str] = "Cancelled by customer"

    model_config = ConfigDict(from_attributes=True)

class OrderReturnRequest(BaseModel):
    reason: str
    quantity: Optional[int] = 1

    model_config = ConfigDict(from_attributes=True)

class OrderActionResponse(BaseModel):
    success: bool
    order_id: str
    status: str
    message: str

    model_config = ConfigDict(from_attributes=True)
