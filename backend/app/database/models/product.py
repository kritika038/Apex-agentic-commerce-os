from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, JSON, Numeric, ForeignKey
from .base import TimeStampedBase, generate_uuid
from typing import Optional

class Product(TimeStampedBase):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    name: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    brand: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    category: Mapped[str] = mapped_column(String, index=True)
    subcategory: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    mrp: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String, default="INR")
    gtin: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    model_number: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    sku: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    image_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    image_urls: Mapped[list] = mapped_column(JSON, default=list)
    rating: Mapped[Optional[float]] = mapped_column(Numeric(3, 2), nullable=True, default=4.5)
    review_count: Mapped[int] = mapped_column(default=0)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    variant_group_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    external_comparison_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    merchant = relationship("Merchant", back_populates="products")
    inventory = relationship("Inventory", back_populates="product", uselist=False, cascade="all, delete-orphan")
    external_offers = relationship("ExternalProductOffer", back_populates="apex_product", cascade="all, delete-orphan")
