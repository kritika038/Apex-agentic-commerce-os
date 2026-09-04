from decimal import Decimal
from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any

class ProductBase(BaseModel):
    name: str
    description: Optional[str] = None
    brand: Optional[str] = None
    category: str
    subcategory: Optional[str] = None
    price: Decimal
    mrp: Optional[Decimal] = None
    currency: str = "INR"
    gtin: Optional[str] = None
    model_number: Optional[str] = None
    sku: Optional[str] = None
    rating: Optional[float] = 4.5
    review_count: Optional[int] = 0
    tags: Optional[list] = []
    attributes: Dict[str, Any] = {}
    external_comparison_enabled: Optional[bool] = True

    model_config = ConfigDict(from_attributes=True)

class ProductCreate(ProductBase):
    stock_quantity: int = 0

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    price: Optional[Decimal] = None
    mrp: Optional[Decimal] = None
    is_active: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)

class ProductResponse(ProductBase):
    id: str
    merchant_id: str
    is_active: bool
    stock_quantity: Optional[int] = None
    in_stock: Optional[bool] = None
    image_url: Optional[str] = None
    lowest_market_price: Optional[float] = None
    external_stores_count: Optional[int] = 0
    variants_count: Optional[int] = 1
    available_colors: Optional[list] = []
    available_sizes: Optional[list] = []
    min_price: Optional[Decimal] = None
    max_price: Optional[Decimal] = None
    variants: Optional[list] = []

    model_config = ConfigDict(from_attributes=True)
