from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from decimal import Decimal
from datetime import datetime

class ExternalStoreInfo(BaseModel):
    id: str
    name: str
    domain: str
    store_type: str
    logo_url: Optional[str] = None
    status: str
    verified: bool

class ExternalProductIdentity(BaseModel):
    brand: Optional[str] = None
    model: Optional[str] = None
    style_code: Optional[str] = None
    color: Optional[str] = None
    size: Optional[str] = None
    asin: Optional[str] = None
    gtin: Optional[str] = None

class ExternalOfferItem(BaseModel):
    id: str
    store_name: str
    store_domain: str
    store_logo_url: Optional[str] = None
    external_url: str
    link_type: str = "SEARCH_FALLBACK" # EXACT, VARIANT_EXACT, MODEL_EXACT, SIMILAR, SEARCH_FALLBACK, UNAVAILABLE
    action_label: str = "Search on Store →"
    redirect_url: str
    price: Optional[float] = None
    mrp: Optional[float] = None
    shipping_price: float = 0.0
    total_price: Optional[float] = None
    currency: str = "INR"
    difference_from_apex: Optional[float] = None # negative if cheaper, positive if more expensive, None if price is unknown
    price_delta_label: Optional[str] = None # e.g. "₹50 cheaper", "Search result — exact product not verified"
    match_type: str # EXACT, VARIANT_EXACT, MODEL_EXACT, SIMILAR, SEARCH_FALLBACK, UNAVAILABLE
    match_confidence: float
    match_reason: Optional[str] = None
    identity_evidence: Optional[Dict[str, Any]] = None
    source_status: str = "VERIFIED" # VERIFIED, CACHED, SEEDED_DEMO, UNAVAILABLE
    source_verified: bool = True
    availability: str = "IN_STOCK" # IN_STOCK, OUT_OF_STOCK, LIMITED_STOCK, UNKNOWN
    observed_at: Optional[Any] = None
    verified_at: Optional[str] = None
    is_lowest: bool = False
    external_product_id: Optional[str] = None
    external_product_title: Optional[str] = None
    external_image_url: Optional[str] = None
    external_product_image: Optional[str] = None
    identity: Optional[ExternalProductIdentity] = None

class CanonicalProductIdentity(BaseModel):
    canonical_product_id: str
    brand: str
    title: str
    category: str
    subcategory: Optional[str] = None
    model: Optional[str] = None
    style_code: Optional[str] = None
    gtin: Optional[str] = None
    color: Optional[str] = None
    size: Optional[str] = None
    variant: Optional[str] = None
    canonical_image_url: str
    verified: bool = True

class PriceComparisonCheckRequest(BaseModel):
    product_id: str
    variant_id: Optional[str] = None
    force_refresh: bool = False

class PriceComparisonResponse(BaseModel):
    product_id: str
    canonical_product: Optional[CanonicalProductIdentity] = None
    product_name: str
    product_brand: Optional[str] = None
    product_category: str
    product_image_url: Optional[str] = None
    apex_price: float
    apex_mrp: Optional[float] = None
    currency: str = "INR"
    offers: List[ExternalOfferItem]
    lowest_verified_price: float
    lowest_store: str
    lowest_verified_retailer: Optional[str] = None
    apex_difference: float
    apex_is_lowest: bool
    checked_sources: int
    checked_at: Any
    verification_scope: str = "checked_stores_only"
    cache_status: str = "LIVE" # LIVE, CACHED
    summary_text: str

class PriceHistoryItem(BaseModel):
    date: str
    price: float
    store_name: str

class PriceHistoryResponse(BaseModel):
    product_id: str
    currency: str = "INR"
    history: List[PriceHistoryItem]
    has_sufficient_data: bool
    message: Optional[str] = None

class OutboundRedirectResponse(BaseModel):
    target_url: str
    store_name: str
    domain: str
    allowed: bool
