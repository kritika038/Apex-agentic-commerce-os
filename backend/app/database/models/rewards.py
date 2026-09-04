from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Numeric, Integer, Boolean, ForeignKey, DateTime, UniqueConstraint, Index
from .base import TimeStampedBase, generate_uuid
from datetime import datetime
from typing import Optional, List

class Coupon(TimeStampedBase):
    __tablename__ = "coupons"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    code: Mapped[str] = mapped_column(String, index=True) # e.g. "SAVE500"
    description: Mapped[str] = mapped_column(String)
    discount_type: Mapped[str] = mapped_column(String, default="FIXED") # "FIXED" or "PERCENTAGE"
    discount_value: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    min_cart_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    max_discount_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    usage_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    per_user_limit: Mapped[int] = mapped_column(Integer, default=1)

    merchant = relationship("Merchant")

    __table_args__ = (
        UniqueConstraint("merchant_id", "code", name="uq_coupon_merchant_code"),
    )

class CouponUsage(TimeStampedBase):
    __tablename__ = "coupon_usages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    coupon_id: Mapped[str] = mapped_column(ForeignKey("coupons.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    order_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    discount_applied: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    coupon = relationship("Coupon")
    user = relationship("User")

class Voucher(TimeStampedBase):
    __tablename__ = "vouchers"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    code: Mapped[str] = mapped_column(String, index=True)
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String)
    discount_type: Mapped[str] = mapped_column(String, default="FIXED")
    discount_value: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    min_cart_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    max_discount_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    merchant = relationship("Merchant")

class UserVoucher(TimeStampedBase):
    __tablename__ = "user_vouchers"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    voucher_id: Mapped[str] = mapped_column(ForeignKey("vouchers.id"), index=True)
    status: Mapped[str] = mapped_column(String, default="AVAILABLE") # "AVAILABLE", "USED", "EXPIRED"
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    order_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)

    user = relationship("User")
    voucher = relationship("Voucher")

class CoinWallet(TimeStampedBase):
    __tablename__ = "coin_wallets"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    balance: Mapped[int] = mapped_column(Integer, default=0)

    user = relationship("User")

class CoinLedger(TimeStampedBase):
    __tablename__ = "coin_ledger"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    amount: Mapped[int] = mapped_column(Integer) # positive for credit, negative for debit
    transaction_type: Mapped[str] = mapped_column(String) # "WELCOME_BONUS", "PURCHASE_REDEEMED", "REFUND", "MANUAL_ADJUSTMENT"
    reference_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    description: Mapped[str] = mapped_column(String)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)

    user = relationship("User")

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_coin_ledger_idempotency"),
    )

class RewardPointsWallet(TimeStampedBase):
    __tablename__ = "reward_points_wallets"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    balance: Mapped[int] = mapped_column(Integer, default=0)

    user = relationship("User")

class RewardPointsLedger(TimeStampedBase):
    __tablename__ = "reward_points_ledger"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    points: Mapped[int] = mapped_column(Integer) # positive for credit, negative for debit
    transaction_type: Mapped[str] = mapped_column(String) # "ORDER_REWARD", "CAMPAIGN_BONUS", "EXPIRATION"
    reference_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    description: Mapped[str] = mapped_column(String)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)

    user = relationship("User")

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_reward_points_ledger_idempotency"),
    )
