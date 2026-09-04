from decimal import Decimal
from datetime import datetime, timezone
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.database.models.cart import Cart
from app.database.models.user import User
from app.database.models.rewards import (
    Coupon,
    CouponUsage,
    Voucher,
    UserVoucher,
    CoinWallet,
    CoinLedger,
    RewardPointsWallet,
    RewardPointsLedger,
)
from app.schemas.rewards import CartPricingResponse

COINS_PER_RUPEE = 10 # 10 Apex Coins = ₹1.00
POINTS_PER_HUNDRED_RUPEES = 1 # 1 Apex Point per ₹100 paid

class PricingService:
    @staticmethod
    def get_or_create_coin_wallet(db: Session, user_id: str) -> CoinWallet:
        wallet = db.query(CoinWallet).filter(CoinWallet.user_id == user_id).first()
        if not wallet:
            # Grant starter balance of 1,250 coins to new customers
            wallet = CoinWallet(user_id=user_id, balance=1250)
            db.add(wallet)
            db.flush()
            ledger = CoinLedger(
                user_id=user_id,
                amount=1250,
                transaction_type="WELCOME_BONUS",
                description="Welcome to Apex Rewards — starter balance",
                idempotency_key=f"welcome_{user_id}"
            )
            db.add(ledger)
            db.commit()
            db.refresh(wallet)
        return wallet

    @staticmethod
    def get_or_create_points_wallet(db: Session, user_id: str) -> RewardPointsWallet:
        wallet = db.query(RewardPointsWallet).filter(RewardPointsWallet.user_id == user_id).first()
        if not wallet:
            wallet = RewardPointsWallet(user_id=user_id, balance=150)
            db.add(wallet)
            db.flush()
            ledger = RewardPointsLedger(
                user_id=user_id,
                points=150,
                transaction_type="WELCOME_BONUS",
                description="Apex Loyalty Tier Activation",
                idempotency_key=f"welcome_pts_{user_id}"
            )
            db.add(ledger)
            db.commit()
            db.refresh(wallet)
        return wallet

    @staticmethod
    def calculate_authoritative_pricing(
        db: Session,
        merchant_id: str,
        session_id: str,
        user: Optional[User] = None,
        coupon_code: Optional[str] = None,
        voucher_code: Optional[str] = None,
        use_coins: bool = False,
        requested_coins: Optional[int] = None
    ) -> CartPricingResponse:
        """
        Deterministic, server-authoritative pricing engine.
        Calculates subtotal, applies verified coupons, checks voucher eligibility,
        computes coin redemption, and calculates reward points to earn.
        """
        # 1. Authoritative Cart & Subtotal
        cart = db.query(Cart).filter(
            Cart.session_id == session_id,
            Cart.merchant_id == merchant_id
        ).first()

        subtotal = Decimal("0.00")
        if cart and cart.items:
            for it in cart.items:
                qty = Decimal(str(it.quantity))
                u_price = Decimal(str(it.unit_price_snapshot))
                subtotal += (qty * u_price)

        if subtotal == Decimal("0.00"):
            return CartPricingResponse(
                subtotal=Decimal("0.00"),
                total=Decimal("0.00"),
                currency=cart.currency if cart else "INR"
            )

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        coupon_discount = Decimal("0.00")
        applied_coupon_code = None

        # Ensure standard coupons and vouchers exist for merchant
        from app.services.reward_service import RewardService
        RewardService.seed_initial_coupons_and_vouchers(db, merchant_id, user.id if user else None)

        # 2. Coupon Validation
        if coupon_code and coupon_code.strip():
            clean_code = coupon_code.strip().upper()
            coupon = db.query(Coupon).filter(
                Coupon.merchant_id == merchant_id,
                Coupon.code == clean_code
            ).first()

            if not coupon or not coupon.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Promo code '{clean_code}' is invalid or inactive."
                )

            if coupon.expires_at and coupon.expires_at < now:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Promo code '{clean_code}' has expired."
                )

            if subtotal < coupon.min_cart_amount:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Minimum order value of ₹{coupon.min_cart_amount:,.2f} required for coupon '{clean_code}'."
                )

            if coupon.usage_limit and coupon.usage_count >= coupon.usage_limit:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Promo code '{clean_code}' usage limit has been reached."
                )

            if user:
                user_usages = db.query(CouponUsage).filter(
                    CouponUsage.coupon_id == coupon.id,
                    CouponUsage.user_id == user.id
                ).count()
                if user_usages >= coupon.per_user_limit:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"You have already redeemed promo code '{clean_code}'."
                    )

            # Compute Discount
            if coupon.discount_type == "PERCENTAGE":
                calc_disc = (subtotal * coupon.discount_value) / Decimal("100.00")
            else:
                calc_disc = coupon.discount_value

            if coupon.max_discount_amount and calc_disc > coupon.max_discount_amount:
                calc_disc = coupon.max_discount_amount

            coupon_discount = min(calc_disc, subtotal)
            applied_coupon_code = coupon.code

        # 3. Voucher Validation
        voucher_discount = Decimal("0.00")
        applied_voucher_code = None

        if voucher_code and voucher_code.strip():
            clean_vouch = voucher_code.strip().upper()
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Please sign in to your account to apply personal vouchers."
                )

            voucher = db.query(Voucher).filter(
                Voucher.merchant_id == merchant_id,
                Voucher.code == clean_vouch,
                Voucher.is_active == True
            ).first()

            if not voucher:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Voucher '{clean_vouch}' is not recognized."
                )

            if voucher.expires_at < now:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Voucher '{clean_vouch}' has expired."
                )

            if subtotal < voucher.min_cart_amount:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Minimum purchase of ₹{voucher.min_cart_amount:,.2f} required for voucher '{clean_vouch}'."
                )

            user_voucher = db.query(UserVoucher).filter(
                UserVoucher.user_id == user.id,
                UserVoucher.voucher_id == voucher.id,
                UserVoucher.status == "AVAILABLE"
            ).first()

            if not user_voucher:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Voucher '{clean_vouch}' is either already redeemed or not available for your account."
                )

            # Compute Voucher Discount
            if voucher.discount_type == "PERCENTAGE":
                v_calc = (subtotal * voucher.discount_value) / Decimal("100.00")
            else:
                v_calc = voucher.discount_value

            if voucher.max_discount_amount and v_calc > voucher.max_discount_amount:
                v_calc = voucher.max_discount_amount

            remaining_after_coupon = max(Decimal("0.00"), subtotal - coupon_discount)
            voucher_discount = min(v_calc, remaining_after_coupon)
            applied_voucher_code = voucher.code

        # 4. Apex Coins Calculation
        coin_balance = 0
        max_coins_redeemable = 0
        coins_used = 0
        coin_discount = Decimal("0.00")

        if user:
            wallet = PricingService.get_or_create_coin_wallet(db, user.id)
            coin_balance = wallet.balance

            remaining_for_coins = max(Decimal("0.00"), subtotal - coupon_discount - voucher_discount)
            max_coins_redeemable = min(coin_balance, int(remaining_for_coins * COINS_PER_RUPEE))

            if use_coins and coin_balance > 0 and max_coins_redeemable > 0:
                if requested_coins is not None and requested_coins > 0:
                    coins_used = min(requested_coins, max_coins_redeemable)
                else:
                    coins_used = max_coins_redeemable

                coin_discount = Decimal(str(coins_used)) / Decimal(str(COINS_PER_RUPEE))

        # 5. Final Authoritative Payable Amount
        final_total = max(
            Decimal("0.00"),
            subtotal - coupon_discount - voucher_discount - coin_discount
        )

        # 6. Points to Earn on Successful Order
        points_to_earn = int(final_total // Decimal("100.00")) * POINTS_PER_HUNDRED_RUPEES

        return CartPricingResponse(
            subtotal=subtotal,
            coupon_code=applied_coupon_code,
            coupon_discount=coupon_discount,
            voucher_code=applied_voucher_code,
            voucher_discount=voucher_discount,
            coins_used=coins_used,
            coin_discount=coin_discount,
            delivery_charges=Decimal("0.00"),
            taxes=Decimal("0.00"),
            total=final_total,
            currency="INR",
            points_to_earn=points_to_earn,
            available_coin_balance=coin_balance,
            max_coins_redeemable=max_coins_redeemable,
            coin_value_inr=Decimal(str(coin_balance)) / Decimal(str(COINS_PER_RUPEE))
        )
