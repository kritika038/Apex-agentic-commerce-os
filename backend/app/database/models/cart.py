from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Numeric, Integer, ForeignKey
from .base import TimeStampedBase, generate_uuid
from typing import List

class Cart(TimeStampedBase):
    __tablename__ = "carts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    session_id: Mapped[str] = mapped_column(String, index=True) # link to shopping session
    status: Mapped[str] = mapped_column(String, default="active")
    currency: Mapped[str] = mapped_column(String, default="INR")
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))

    items: Mapped[List["CartItem"]] = relationship("CartItem", back_populates="cart", cascade="all, delete-orphan")
    merchant = relationship("Merchant")

class CartItem(TimeStampedBase):
    __tablename__ = "cart_items"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    cart_id: Mapped[str] = mapped_column(ForeignKey("carts.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price_snapshot: Mapped[Decimal] = mapped_column(Numeric(12, 2)) # Server authoritative price at time of adding

    cart: Mapped["Cart"] = relationship("Cart", back_populates="items")
    product = relationship("Product")
