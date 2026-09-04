from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, JSON
from .base import TimeStampedBase, generate_uuid
from typing import Optional, List

class ExternalStore(TimeStampedBase):
    """
    Registry of external stores, marketplaces, and brand official destinations.
    """
    __tablename__ = "external_stores"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String, unique=True, index=True) # e.g. "Amazon India", "Flipkart", "Nike Official"
    domain: Mapped[str] = mapped_column(String, unique=True, index=True) # e.g. "amazon.in", "flipkart.com", "nike.com"
    store_type: Mapped[str] = mapped_column(String, default="RETAILER") # RETAILER, OFFICIAL_BRAND, MARKETPLACE
    country: Mapped[str] = mapped_column(String, default="IN")
    currency: Mapped[str] = mapped_column(String, default="INR")
    logo_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="DEMO_VERIFIED") # LIVE, DEMO_VERIFIED, OFFICIAL_LINK_ONLY, UNAVAILABLE
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=True)
    supports_product_links: Mapped[bool] = mapped_column(Boolean, default=True)
    supports_api: Mapped[bool] = mapped_column(Boolean, default=False)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)

    offers = relationship("ExternalProductOffer", back_populates="external_store", cascade="all, delete-orphan")
    outbound_clicks = relationship("ExternalOutboundClick", back_populates="external_store")
