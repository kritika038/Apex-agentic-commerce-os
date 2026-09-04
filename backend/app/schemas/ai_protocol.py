from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from app.schemas.commerce import BuyerConstraints, PurchaseIntentItem, RecommendationResponse

class AIProtocolMessage(BaseModel):
    type: str
    trace_id: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class BuyerShoppingRequestMessage(AIProtocolMessage):
    type: str = "SHOPPING_REQUEST"
    buyer_id: str
    session_id: str
    message: str
    constraints: Optional[BuyerConstraints] = None

class MerchantProductResponseMessage(AIProtocolMessage):
    type: str = "PRODUCT_RESPONSE"
    session_id: str
    message: str
    products: List[Dict[str, Any]] = []
    cart: Dict[str, Any] = {}
    recommendations: List[RecommendationResponse] = []
    constraints_satisfied: bool = True

class PurchaseIntentMessage(AIProtocolMessage):
    type: str = "PURCHASE_INTENT"
    id: str
    cart_id: str
    status: str
    items: List[PurchaseIntentItem]
    requested_amount: float
    currency: str
    expires_at: Optional[str] = None
