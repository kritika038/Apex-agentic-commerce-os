from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime

class CouponResponse(BaseModel):
    code: str
    description: str
    discount_type: str
    discount_value: Decimal
    min_cart_amount: Decimal
    max_discount_amount: Optional[Decimal] = None
    is_active: bool
    expires_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class VoucherResponse(BaseModel):
    id: str
    code: str
    title: str
    description: str
    discount_type: str
    discount_value: Decimal
    min_cart_amount: Decimal
    max_discount_amount: Optional[Decimal] = None
    expires_at: datetime
    status: str = "AVAILABLE" # "AVAILABLE", "USED", "EXPIRED"

    model_config = ConfigDict(from_attributes=True)

class CartPricingRequest(BaseModel):
    session_id: str
    coupon_code: Optional[str] = None
    voucher_code: Optional[str] = None
    use_coins: bool = False
    coins_to_redeem: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

class CartPricingResponse(BaseModel):
    subtotal: Decimal
    coupon_code: Optional[str] = None
    coupon_discount: Decimal = Decimal("0.00")
    voucher_code: Optional[str] = None
    voucher_discount: Decimal = Decimal("0.00")
    coins_used: int = 0
    coin_discount: Decimal = Decimal("0.00")
    delivery_charges: Decimal = Decimal("0.00")
    taxes: Decimal = Decimal("0.00")
    total: Decimal
    currency: str = "INR"
    points_to_earn: int = 0
    available_coin_balance: int = 0
    max_coins_redeemable: int = 0
    coin_value_inr: Decimal = Decimal("0.00")

    model_config = ConfigDict(from_attributes=True)

class CoinLedgerEntry(BaseModel):
    id: str
    amount: int # +credit, -debit
    transaction_type: str
    reference_id: Optional[str] = None
    description: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class RewardPointsLedgerEntry(BaseModel):
    id: str
    points: int # +credit, -debit
    transaction_type: str
    reference_id: Optional[str] = None
    description: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class CustomerRewardsSummary(BaseModel):
    coin_balance: int
    estimated_coin_value_inr: Decimal
    points_balance: int
    conversion_rate_description: str = "10 Apex Coins = ₹1.00"
    earning_rule_description: str = "1 Apex Point earned per ₹100 paid"
    available_vouchers: List[VoucherResponse] = []
    coin_history: List[CoinLedgerEntry] = []
    points_history: List[RewardPointsLedgerEntry] = []

    model_config = ConfigDict(from_attributes=True)
