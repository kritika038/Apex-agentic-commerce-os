from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, JSON, DateTime
from .base import TimeStampedBase, generate_uuid

class CanonicalProduct(TimeStampedBase):
    """
    Canonical Product Identity Layer (Buyhatke-style multi-retailer anchor).
    Defines the ground-truth physical product identity (Brand, Model, Style Code, GTIN, Variant)
    that unifies retailer listings across stores.
    """
    __tablename__ = "canonical_products"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    brand: Mapped[str] = mapped_column(String, index=True)
    title: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String, index=True)
    subcategory: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    style_code: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    gtin: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    color: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    size: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    variant: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    canonical_image_url: Mapped[str] = mapped_column(String)
    verified: Mapped[bool] = mapped_column(Boolean, default=True)
    attributes_json: Mapped[dict] = mapped_column(JSON, default=dict)
