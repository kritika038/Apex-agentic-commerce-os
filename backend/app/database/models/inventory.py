from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, ForeignKey
from .base import TimeStampedBase, generate_uuid

class Inventory(TimeStampedBase):
    __tablename__ = "inventory"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), unique=True, index=True)
    stock_quantity: Mapped[int] = mapped_column(Integer, default=0)
    reserved_quantity: Mapped[int] = mapped_column(Integer, default=0)
    
    product: Mapped["Product"] = relationship("Product", back_populates="inventory")
    merchant: Mapped["Merchant"] = relationship("Merchant")
