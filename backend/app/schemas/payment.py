from pydantic import BaseModel, Field
from decimal import Decimal
from typing import Optional
from datetime import datetime

class PaymentCreateOrderRequest(BaseModel):
    purchase_intent_id: str = Field(..., description="ID of the Purchase Intent")
    authorization_id: str = Field(..., description="ID of the valid Transaction Authorization")
    idempotency_key: Optional[str] = Field(None, description="Client or caller idempotency key")
    expected_amount: Optional[Decimal] = Field(None, description="Optional expected amount to guard against client tampering")
    expected_currency: Optional[str] = Field(None, description="Optional expected currency to guard against client tampering")

class PaymentOrderResponse(BaseModel):
    payment_transaction_id: str
    razorpay_order_id: Optional[str] = None
    amount: Decimal
    amount_minor: Optional[int] = None
    currency: str
    status: str
    receipt: str
    key_id: Optional[str] = None
    razorpay_key_id: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}

class PaymentTransactionResponse(BaseModel):
    id: str
    merchant_id: str
    purchase_intent_id: str
    authorization_id: str
    razorpay_order_id: Optional[str] = None
    razorpay_payment_id: Optional[str] = None
    amount: Decimal
    currency: str
    status: str
    idempotency_key: str
    receipt: str
    attempt_count: int
    failure_code: Optional[str] = None
    failure_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    authorized_at: Optional[datetime] = None
    captured_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

class PaymentReconcileResponse(BaseModel):
    transaction_id: str
    previous_status: str
    current_status: str
    reconciled_via: str
    message: str

class MockPaymentSimulateRequest(BaseModel):
    outcome: str = Field("SUCCESS", description="Outcome to simulate: SUCCESS, FAILURE, TIMEOUT")

class PaymentVerifySignatureRequest(BaseModel):
    payment_transaction_id: Optional[str] = Field(None, description="Optional payment transaction id")
    razorpay_order_id: str = Field(..., description="Razorpay order ID returned by gateway")
    razorpay_payment_id: str = Field(..., description="Razorpay payment ID returned by gateway")
    razorpay_signature: str = Field(..., description="Cryptographic payment signature returned by Razorpay Checkout")

class PaymentConfigResponse(BaseModel):
    configured: bool = Field(..., description="Whether real Razorpay credentials are configured in backend")
    key_id: Optional[str] = Field(None, description="Public Razorpay Key ID (never key secret)")
    mode: str = Field(..., description="test or live")
    provider: str = Field(..., description="razorpay or mock")
    currency: str = Field("INR", description="Default checkout currency")

