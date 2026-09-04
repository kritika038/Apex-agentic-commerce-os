from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, JSON, ForeignKey
from .base import TimeStampedBase, generate_uuid
from typing import Optional

class ProductInteraction(TimeStampedBase):
    """
    Persisted customer interaction events for grounding personalization:
    Events: PRODUCT_VIEW, SEARCH, ADD_TO_CART, PURCHASE, FIT_CHECK.
    """
    __tablename__ = "product_interactions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    session_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    event_type: Mapped[str] = mapped_column(String, index=True) # PRODUCT_VIEW, SEARCH, ADD_TO_CART, PURCHASE, FIT_CHECK
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    merchant = relationship("Merchant")
    user = relationship("User")
    product = relationship("Product")
