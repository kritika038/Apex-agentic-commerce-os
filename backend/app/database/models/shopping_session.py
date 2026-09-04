from typing import Optional, Dict, Any
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, ForeignKey, JSON
from .base import TimeStampedBase, generate_uuid

class ShoppingSession(TimeStampedBase):
    __tablename__ = "shopping_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    customer_identifier: Mapped[str] = mapped_column(String, index=True) # e.g. email or anonymous id
    status: Mapped[str] = mapped_column(String, default="active")
    context_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict)
