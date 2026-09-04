from decimal import Decimal
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, JSON, Numeric, ForeignKey, DateTime, Float
from .base import TimeStampedBase, generate_uuid

class ExternalProductOffer(TimeStampedBase):
    """
    Verified external offers mapped to specific Apex products.
    Stores observed prices, match classifications, and verified outbound URLs.
    """
    __tablename__ = "external_product_offers"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    apex_product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    external_store_id: Mapped[str] = mapped_column(ForeignKey("external_stores.id"), index=True)
    
    external_product_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    external_product_title: Mapped[str] = mapped_column(String)
    external_url: Mapped[str] = mapped_column(String)
    affiliate_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    mrp: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String, default="INR")
    shipping_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    tax_included: Mapped[bool] = mapped_column(Boolean, default=True)
    availability: Mapped[str] = mapped_column(String, default="IN_STOCK") # IN_STOCK, OUT_OF_STOCK, LIMITED_STOCK, UNKNOWN
    
    match_type: Mapped[str] = mapped_column(String, default="EXACT") # EXACT, VARIANT_EXACT, HIGH_CONFIDENCE, SIMILAR
    match_confidence: Mapped[float] = mapped_column(Float, default=1.0)
    match_reason: Mapped[Optional[str]] = mapped_column(String, nullable=True) # e.g. "Exact GTIN match"
    source_status: Mapped[str] = mapped_column(String, default="VERIFIED") # VERIFIED, CACHED, SEEDED_DEMO, UNAVAILABLE
    source_verified: Mapped[bool] = mapped_column(Boolean, default=True)
    
    observed_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    attributes_json: Mapped[dict] = mapped_column(JSON, default=dict)

    apex_product = relationship("Product", back_populates="external_offers")
    external_store = relationship("ExternalStore", back_populates="offers")
    outbound_clicks = relationship("ExternalOutboundClick", back_populates="external_offer")


class PriceObservationHistory(TimeStampedBase):
    """
    Historical record of observed prices for trend analysis (7d, 30d, 90d).
    """
    __tablename__ = "price_observation_history"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    apex_product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    external_store_id: Mapped[str] = mapped_column(ForeignKey("external_stores.id"), index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String, default="INR")
    observed_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), index=True)
    source_status: Mapped[str] = mapped_column(String, default="VERIFIED")

    apex_product = relationship("Product")
    external_store = relationship("ExternalStore")


class ExternalOutboundClick(TimeStampedBase):
    """
    Audit log of user clicks redirecting to external retailers.
    """
    __tablename__ = "external_outbound_clicks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    external_offer_id: Mapped[str] = mapped_column(ForeignKey("external_product_offers.id"), index=True)
    apex_product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    external_store_id: Mapped[str] = mapped_column(ForeignKey("external_stores.id"), index=True)
    
    target_url: Mapped[str] = mapped_column(String)
    user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    session_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    clicked_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    external_offer = relationship("ExternalProductOffer", back_populates="outbound_clicks")
    external_store = relationship("ExternalStore", back_populates="outbound_clicks")
