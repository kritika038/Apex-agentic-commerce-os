from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database.session import get_db
from app.database.models.user import User
from app.database.models.merchant import Merchant
from app.auth.deps import get_current_user, get_optional_current_user
from app.schemas.rewards import (
    CouponResponse,
    CartPricingRequest,
    CartPricingResponse,
    CustomerRewardsSummary,
)
from app.services.pricing_service import PricingService
from app.services.reward_service import RewardService

router = APIRouter(tags=["Rewards & Pricing"])

def _resolve_merchant(db: Session, merchant_id: Optional[str] = None) -> Merchant:
    if merchant_id:
        merchant = db.query(Merchant).filter(Merchant.id == merchant_id).first()
        if not merchant:
            raise HTTPException(status_code=404, detail="Merchant not found.")
        return merchant
    merchant = db.query(Merchant).first()
    if not merchant:
        raise HTTPException(status_code=404, detail="No active merchant found.")
    return merchant

@router.get("/coupons", response_model=List[CouponResponse])
def get_active_coupons(
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Retrieves currently active coupons and promo codes for the store.
    """
    merchant = _resolve_merchant(db, merchant_id)
    return RewardService.get_public_coupons(db=db, merchant_id=merchant.id)

@router.get("/me", response_model=CustomerRewardsSummary)
def get_customer_rewards(
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves the authenticated customer's Apex Coins balance, Loyalty Points balance,
    eligible vouchers, and rewards ledger history.
    """
    merchant = _resolve_merchant(db, merchant_id)
    return RewardService.get_customer_rewards_summary(
        db=db,
        user=current_user,
        merchant_id=merchant.id
    )

@router.post("/calculate-pricing", response_model=CartPricingResponse)
def calculate_cart_pricing(
    payload: CartPricingRequest,
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Authoritative server-side pricing breakdown calculator.
    Validates promo codes, voucher eligibility, and coin redemption against live database rules.
    """
    merchant = _resolve_merchant(db, merchant_id)
    return PricingService.calculate_authoritative_pricing(
        db=db,
        merchant_id=merchant.id,
        session_id=payload.session_id,
        user=current_user,
        coupon_code=payload.coupon_code,
        voucher_code=payload.voucher_code,
        use_coins=payload.use_coins,
        requested_coins=payload.coins_to_redeem
    )
