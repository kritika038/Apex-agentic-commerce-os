from decimal import Decimal
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

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
from app.schemas.rewards import (
    CouponResponse,
    VoucherResponse,
    CoinLedgerEntry,
    RewardPointsLedgerEntry,
    CustomerRewardsSummary,
)
from app.services.pricing_service import PricingService, COINS_PER_RUPEE

class RewardService:
    @staticmethod
    def seed_initial_coupons_and_vouchers(db: Session, merchant_id: str, user_id: Optional[str] = None):
        """
        Seeds standard coupons and customer vouchers if not already present.
        """
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        future_date = now + timedelta(days=90)

        # 1. Standard Store Coupons
        existing_save500 = db.query(Coupon).filter(Coupon.merchant_id == merchant_id, Coupon.code == "SAVE500").first()
        if not existing_save500:
            db.add(Coupon(
                merchant_id=merchant_id,
                code="SAVE500",
                description="Flat ₹500 discount on orders above ₹2,500",
                discount_type="FIXED",
                discount_value=Decimal("500.00"),
                min_cart_amount=Decimal("2500.00"),
                max_discount_amount=Decimal("500.00"),
                expires_at=future_date,
                is_active=True,
                per_user_limit=2
            ))

        existing_apex10 = db.query(Coupon).filter(Coupon.merchant_id == merchant_id, Coupon.code == "APEX10").first()
        if not existing_apex10:
            db.add(Coupon(
                merchant_id=merchant_id,
                code="APEX10",
                description="10% discount up to ₹1,000 on athletic gear",
                discount_type="PERCENTAGE",
                discount_value=Decimal("10.00"),
                min_cart_amount=Decimal("1500.00"),
                max_discount_amount=Decimal("1000.00"),
                expires_at=future_date,
                is_active=True,
                per_user_limit=5
            ))

        existing_welcome = db.query(Coupon).filter(Coupon.merchant_id == merchant_id, Coupon.code == "WELCOME200").first()
        if not existing_welcome:
            db.add(Coupon(
                merchant_id=merchant_id,
                code="WELCOME200",
                description="Welcome bonus: ₹200 off on your order above ₹1,000",
                discount_type="FIXED",
                discount_value=Decimal("200.00"),
                min_cart_amount=Decimal("1000.00"),
                max_discount_amount=Decimal("200.00"),
                expires_at=future_date,
                is_active=True,
                per_user_limit=1
            ))

        # 2. Vouchers
        v1 = db.query(Voucher).filter(Voucher.merchant_id == merchant_id, Voucher.code == "VOUCH500").first()
        if not v1:
            v1 = Voucher(
                merchant_id=merchant_id,
                code="VOUCH500",
                title="₹500 OFF Premium Reward Voucher",
                description="Exclusive VIP reward voucher for purchases above ₹3,000",
                discount_type="FIXED",
                discount_value=Decimal("500.00"),
                min_cart_amount=Decimal("3000.00"),
                max_discount_amount=Decimal("500.00"),
                expires_at=future_date,
                is_active=True
            )
            db.add(v1)
            db.flush()

        v2 = db.query(Voucher).filter(Voucher.merchant_id == merchant_id, Voucher.code == "SPRINT10").first()
        if not v2:
            v2 = Voucher(
                merchant_id=merchant_id,
                code="SPRINT10",
                title="10% OFF Sprint Pass",
                description="10% discount on marathon running gear (max ₹1,000)",
                discount_type="PERCENTAGE",
                discount_value=Decimal("10.00"),
                min_cart_amount=Decimal("2000.00"),
                max_discount_amount=Decimal("1000.00"),
                expires_at=future_date,
                is_active=True
            )
            db.add(v2)
            db.flush()

        # 3. Assign Vouchers to User if given
        if user_id:
            for v in [v1, v2]:
                if v:
                    uv = db.query(UserVoucher).filter(
                        UserVoucher.user_id == user_id,
                        UserVoucher.voucher_id == v.id
                    ).first()
                    if not uv:
                        db.add(UserVoucher(
                            user_id=user_id,
                            voucher_id=v.id,
                            status="AVAILABLE"
                        ))

        db.commit()

    @staticmethod
    def get_customer_rewards_summary(db: Session, user: User, merchant_id: str) -> CustomerRewardsSummary:
        """
        Builds the unified loyalty & rewards dashboard summary for the authenticated customer.
        """
        RewardService.seed_initial_coupons_and_vouchers(db, merchant_id, user.id)

        coin_wallet = PricingService.get_or_create_coin_wallet(db, user.id)
        points_wallet = PricingService.get_or_create_points_wallet(db, user.id)

        # Available Vouchers for this user
        user_vouchers = (
            db.query(UserVoucher)
            .join(Voucher, UserVoucher.voucher_id == Voucher.id)
            .filter(UserVoucher.user_id == user.id, UserVoucher.status == "AVAILABLE")
            .all()
        )

        voucher_list: List[VoucherResponse] = []
        for uv in user_vouchers:
            v = uv.voucher
            if v and v.is_active:
                voucher_list.append(
                    VoucherResponse(
                        id=v.id,
                        code=v.code,
                        title=v.title,
                        description=v.description,
                        discount_type=v.discount_type,
                        discount_value=v.discount_value,
                        min_cart_amount=v.min_cart_amount,
                        max_discount_amount=v.max_discount_amount,
                        expires_at=v.expires_at,
                        status=uv.status
                    )
                )

        # Coin Activity History
        coin_entries = (
            db.query(CoinLedger)
            .filter(CoinLedger.user_id == user.id)
            .order_by(CoinLedger.created_at.desc())
            .limit(30)
            .all()
        )
        coin_history = [
            CoinLedgerEntry(
                id=c.id,
                amount=c.amount,
                transaction_type=c.transaction_type,
                reference_id=c.reference_id,
                description=c.description,
                created_at=c.created_at
            )
            for c in coin_entries
        ]

        # Reward Points Activity History
        points_entries = (
            db.query(RewardPointsLedger)
            .filter(RewardPointsLedger.user_id == user.id)
            .order_by(RewardPointsLedger.created_at.desc())
            .limit(30)
            .all()
        )
        points_history = [
            RewardPointsLedgerEntry(
                id=p.id,
                points=p.points,
                transaction_type=p.transaction_type,
                reference_id=p.reference_id,
                description=p.description,
                created_at=p.created_at
            )
            for p in points_entries
        ]

        return CustomerRewardsSummary(
            coin_balance=coin_wallet.balance,
            estimated_coin_value_inr=Decimal(str(coin_wallet.balance)) / Decimal(str(COINS_PER_RUPEE)),
            points_balance=points_wallet.balance,
            conversion_rate_description="10 Apex Coins = ₹1.00",
            earning_rule_description="1 Apex Point earned per ₹100 paid",
            available_vouchers=voucher_list,
            coin_history=coin_history,
            points_history=points_history
        )

    @staticmethod
    def get_public_coupons(db: Session, merchant_id: str) -> List[CouponResponse]:
        """
        Retrieves active coupons for storefront display.
        """
        RewardService.seed_initial_coupons_and_vouchers(db, merchant_id)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        coupons = (
            db.query(Coupon)
            .filter(
                Coupon.merchant_id == merchant_id,
                Coupon.is_active == True,
                (Coupon.expires_at == None) | (Coupon.expires_at >= now)
            )
            .all()
        )
        return [
            CouponResponse(
                code=c.code,
                description=c.description,
                discount_type=c.discount_type,
                discount_value=c.discount_value,
                min_cart_amount=c.min_cart_amount,
                max_discount_amount=c.max_discount_amount,
                is_active=c.is_active,
                expires_at=c.expires_at
            )
            for c in coupons
        ]

    @staticmethod
    def apply_post_payment_rewards(
        db: Session,
        merchant_id: str,
        user_id: str,
        order_reference: str,
        payment_transaction_id: str,
        pricing_data: Dict[str, Any]
    ):
        """
        Idempotently executes all reward mutations after Razorpay signature verification.
        1. Debits redeemed Apex Coins & writes CoinLedger.
        2. Consumes applied Voucher & marks UserVoucher as USED.
        3. Records CouponUsage and increments coupon usage count.
        4. Awards earned Apex Points & writes RewardPointsLedger.
        """
        if not user_id:
            return

        # 1. Apex Coins Redemption
        coins_used = int(pricing_data.get("coins_used", 0))
        if coins_used > 0:
            coin_idem = f"coin_redeem_{payment_transaction_id}"
            existing_coin_tx = db.query(CoinLedger).filter(CoinLedger.idempotency_key == coin_idem).first()
            if not existing_coin_tx:
                wallet = PricingService.get_or_create_coin_wallet(db, user_id)
                # Enforce no negative balances
                wallet.balance = max(0, wallet.balance - coins_used)
                coin_entry = CoinLedger(
                    user_id=user_id,
                    amount=-coins_used,
                    transaction_type="PURCHASE_REDEEMED",
                    reference_id=order_reference,
                    description=f"Redeemed {coins_used} Apex Coins on Order #{order_reference}",
                    idempotency_key=coin_idem
                )
                db.add(coin_entry)

        # 2. Voucher Consumption
        voucher_code = pricing_data.get("voucher_code")
        if voucher_code:
            vouch = db.query(Voucher).filter(Voucher.merchant_id == merchant_id, Voucher.code == voucher_code).first()
            if vouch:
                user_vouch = db.query(UserVoucher).filter(
                    UserVoucher.user_id == user_id,
                    UserVoucher.voucher_id == vouch.id,
                    UserVoucher.status == "AVAILABLE"
                ).first()
                if user_vouch:
                    user_vouch.status = "USED"
                    user_vouch.used_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    user_vouch.order_id = order_reference

        # 3. Coupon Usage Tracking
        coupon_code = pricing_data.get("coupon_code")
        coupon_discount = Decimal(str(pricing_data.get("coupon_discount", 0)))
        if coupon_code:
            coupon = db.query(Coupon).filter(Coupon.merchant_id == merchant_id, Coupon.code == coupon_code).first()
            if coupon:
                coupon.usage_count = (coupon.usage_count or 0) + 1
                usage_entry = CouponUsage(
                    coupon_id=coupon.id,
                    user_id=user_id,
                    order_id=order_reference,
                    discount_applied=coupon_discount
                )
                db.add(usage_entry)

        # 4. Loyalty Apex Points Credit
        points_to_earn = int(pricing_data.get("points_to_earn", 0))
        if points_to_earn > 0:
            points_idem = f"pts_earn_{payment_transaction_id}"
            existing_pts_tx = db.query(RewardPointsLedger).filter(RewardPointsLedger.idempotency_key == points_idem).first()
            if not existing_pts_tx:
                pts_wallet = PricingService.get_or_create_points_wallet(db, user_id)
                pts_wallet.balance += points_to_earn
                pts_entry = RewardPointsLedger(
                    user_id=user_id,
                    points=points_to_earn,
                    transaction_type="ORDER_REWARD",
                    reference_id=order_reference,
                    description=f"Earned {points_to_earn} Apex Points on Order #{order_reference}",
                    idempotency_key=points_idem
                )
                db.add(pts_entry)

        try:
            db.commit()
        except IntegrityError:
            db.rollback()
