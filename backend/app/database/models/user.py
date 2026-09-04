from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, ForeignKey
from .base import TimeStampedBase, generate_uuid
from typing import Optional

class User(TimeStampedBase):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    merchant_id: Mapped[Optional[str]] = mapped_column(ForeignKey("merchants.id"), index=True, nullable=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String)
    full_name: Mapped[str] = mapped_column(String)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    role: Mapped[str] = mapped_column(String, default="admin") # 'admin', 'operator', etc.

    merchant: Mapped[Optional["Merchant"]] = relationship("Merchant", back_populates="users")
