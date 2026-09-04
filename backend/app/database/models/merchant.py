from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, JSON
from .base import TimeStampedBase, generate_uuid
from typing import List

class Merchant(TimeStampedBase):
    __tablename__ = "merchants"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String, index=True)
    domain: Mapped[str] = mapped_column(String, unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)

    users: Mapped[List["User"]] = relationship("User", back_populates="merchant", cascade="all, delete-orphan")
    products: Mapped[List["Product"]] = relationship("Product", back_populates="merchant", cascade="all, delete-orphan")
