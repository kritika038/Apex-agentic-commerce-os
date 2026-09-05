from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

class ShoppingIntent(BaseModel):
    category: Optional[str] = Field(None, description="Category of the product")
    search_query: Optional[str] = Field(None, description="Keywords to search for")
    min_price: Optional[float] = Field(None, description="Minimum price constraint")
    max_price: Optional[float] = Field(None, description="Maximum price constraint")
    currency: str = Field("INR", description="Currency code")
    quantity: int = Field(1, ge=1, description="Quantity desired")
    preferences: List[str] = Field(default_factory=list, description="Specific features or preferences")

    model_config = ConfigDict(from_attributes=True)

class ChatMessage(BaseModel):
    role: str # "user", "assistant", "system", "tool"
    content: str
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class ChatRequest(BaseModel):
    session_id: str
    message: str
    merchant_id: Optional[str] = None
    trace_id: Optional[str] = None
    product_id: Optional[str] = None
    delivery_address: Optional[Dict[str, Any]] = None
    applied_coupon: Optional[str] = None
    applied_voucher: Optional[str] = None
    use_coins: bool = False

    model_config = ConfigDict(from_attributes=True)

class OrderReviewItem(BaseModel):
    product_id: str
    name: str
    quantity: int
    price: float
    subtotal: float
    category: Optional[str] = None
    image_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class OrderReview(BaseModel):
    items: List[OrderReviewItem] = []
    subtotal: float
    coupon_code: Optional[str] = None
    coupon_discount: float = 0.0
    voucher_code: Optional[str] = None
    voucher_discount: float = 0.0
    coins_used: int = 0
    coin_discount: float = 0.0
    shipping: float = 0.0
    total: float
    currency: str = "INR"
    delivery_address: Optional[Dict[str, Any]] = None
    delivery_address_required: bool = False
    autonomous_threshold: float = 5000.0
    is_above_threshold: bool = False
    potential_points: int = 0

    model_config = ConfigDict(from_attributes=True)

class ChatResponse(BaseModel):
    session_id: str
    message: str
    reply: Optional[str] = None
    products: List[Dict[str, Any]] = []
    cart: Dict[str, Any] = {}
    recommendations: List[Dict[str, Any]] = []
    actions: List[str] = []
    structured_intent: Optional[Dict[str, Any]] = None
    order_review: Optional[OrderReview] = None
    requires_approval: bool = False
    approval_details: Optional[Dict[str, Any]] = None
    trace_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
