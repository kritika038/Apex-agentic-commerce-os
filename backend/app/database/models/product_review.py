from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Boolean, ForeignKey
from .base import TimeStampedBase, generate_uuid
from typing import Optional

class ProductReview(TimeStampedBase):
    """
    Persisted real customer reviews for review intelligence and fit feedback.
    """
    __tablename__ = "product_reviews"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    rating: Mapped[int] = mapped_column(Integer, default=5)
    headline: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    review_text: Mapped[str] = mapped_column(String)
    fit_feedback: Mapped[Optional[str]] = mapped_column(String, nullable=True) # TRUE_TO_SIZE, RUNS_SMALL, RUNS_LARGE, NARROW
    verified_purchase: Mapped[bool] = mapped_column(Boolean, default=True)
    helpful_votes: Mapped[int] = mapped_column(Integer, default=0)

    product = relationship("Product")
    user = relationship("User")
