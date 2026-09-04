from decimal import Decimal
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class NegotiationStartRequest(BaseModel):
    product_id: str = Field(..., description="ID of the product to negotiate on")
    quantity: int = Field(1, ge=1, le=100, description="Quantity requested")
    requested_unit_price: Optional[Decimal] = Field(None, gt=0, description="Requested unit price")
    requested_total: Optional[Decimal] = Field(None, gt=0, description="Requested total price (if unit price not provided)")
    customer_id: str = Field("cust_default", description="Customer / Buyer identity")
    buyer_agent_id: Optional[str] = Field("buyer-agent-standard", description="Buyer agent identifier")
    buyer_note: Optional[str] = Field(None, description="Buyer's negotiation rationale or pitch")


class CustomerActionRequest(BaseModel):
    customer_id: str = Field("cust_default", description="Customer identity verifying ownership")
    reason: Optional[str] = Field(None, description="Optional customer reason")


class MerchantApproveRequest(BaseModel):
    merchant_id: str = Field("merch_default", description="Merchant identity")
    reason: Optional[str] = Field(None, description="Approval justification")


class MerchantCounterRequest(BaseModel):
    merchant_id: str = Field("merch_default", description="Merchant identity")
    counter_unit_price: Optional[Decimal] = Field(None, gt=0, description="Merchant counter unit price")
    counter_total: Optional[Decimal] = Field(None, gt=0, description="Merchant counter total price")
    reason: Optional[str] = Field(None, description="Counter offer justification")


class MerchantRejectRequest(BaseModel):
    merchant_id: str = Field("merch_default", description="Merchant identity")
    reason: Optional[str] = Field(None, description="Rejection reason")


class NegotiationCheckoutRequest(BaseModel):
    customer_id: str = Field("cust_default", description="Customer identity verifying ownership")
    payment_method: Optional[str] = Field("upi", description="Payment method to initialize checkout with")


class NegotiatedOfferResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    offer_code: str
    negotiation_id: Optional[str] = None
    merchant_id: str
    customer_id: str
    product_id: str
    product_name: Optional[str] = None
    quantity: int
    list_unit_price: Decimal
    list_total: Decimal
    requested_unit_price: Decimal
    requested_total: Decimal
    offered_unit_price: Decimal
    offered_total: Decimal
    discount_amount: Decimal
    discount_percent: Decimal
    final_total: Decimal
    currency: str
    status: str
    reason: Optional[str] = None
    expires_at: datetime
    created_at: datetime
    is_active: bool
    requires_human_approval: bool
    customer_accepted: bool
    customer_accepted_at: Optional[datetime] = None
    customer_rejected_at: Optional[datetime] = None
    approval_request_id: Optional[str] = None
    transaction_authorization_id: Optional[str] = None
    payment_order_id: Optional[str] = None
    payment_status: Optional[str] = None
    order_id: Optional[str] = None
    audit_hash: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None


class NegotiationPolicyUpdate(BaseModel):
    name: Optional[str] = None
    enabled: Optional[bool] = None
    max_discount_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    max_discount_amount: Optional[Decimal] = Field(None, ge=0)
    auto_accept_below_discount_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    approval_above_discount_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    max_quantity: Optional[int] = Field(None, ge=1)
    min_order_value: Optional[Decimal] = Field(None, ge=0)
    allowed_categories: Optional[List[str]] = None
    allowed_products: Optional[List[str]] = None
    offer_ttl_minutes: Optional[int] = Field(None, ge=1, le=1440)
    is_active: Optional[bool] = None


class NegotiationPolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    merchant_id: str
    tenant_id: str
    name: str
    enabled: bool
    max_discount_percent: Decimal
    max_discount_amount: Decimal
    auto_accept_below_discount_percent: Decimal
    approval_above_discount_percent: Decimal
    max_quantity: int
    min_order_value: Decimal
    allowed_categories: List[str]
    allowed_products: List[str]
    currency: str
    offer_ttl_minutes: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
