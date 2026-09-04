from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Float, ForeignKey
from .base import TimeStampedBase, generate_uuid
from typing import Optional

class Recommendation(TimeStampedBase):
    __tablename__ = "recommendations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    session_id: Mapped[str] = mapped_column(String, index=True)
    agent_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    agent_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    type: Mapped[str] = mapped_column(String) # UPSELL, CROSS_SELL, BUNDLE
    source_product_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    recommended_product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    reason: Mapped[str] = mapped_column(String)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String, default="GENERATED", index=True) # GENERATED, SHOWN, ACCEPTED, REJECTED, EXPIRED
    trace_id: Mapped[Optional[str]] = mapped_column(String, index=True, nullable=True)

    product = relationship("Product")
    merchant = relationship("Merchant")
