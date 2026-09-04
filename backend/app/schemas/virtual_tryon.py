from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class TryOnEligibilityRequest(BaseModel):
    product_id: str
    variant_id: Optional[str] = None

class TryOnEligibilityResponse(BaseModel):
    supported: bool
    product_id: str
    product_name: str
    garment_type: Optional[str] = None  # CLOTHING, FOOTWEAR
    category: Optional[str] = None
    subcategory: Optional[str] = None
    reason: str
    recommended_photo_type: str  # "full_body", "feet_visible", "upper_body"
    product_image_url: Optional[str] = None
    color: Optional[str] = None
    size: Optional[str] = None

class StyleRecommendationItem(BaseModel):
    product_id: str
    name: str
    brand: Optional[str] = None
    price: float
    mrp: Optional[float] = None
    category: str
    subcategory: Optional[str] = None
    image_url: Optional[str] = None
    styling_reason: str
    vto_eligible: bool = True

class TryOnJobStatusResponse(BaseModel):
    job_id: str
    status: str  # CREATED, PROCESSING, COMPLETED, FAILED, EXPIRED, CANCELLED
    progress_percent: int = 0
    processing_stage: str = "PREPARING"  # PREPARING, GARMENT_VALIDATION, POSE_DETECTION, GARMENT_PREPARATION, DIFFUSION, FINALIZING, COMPLETED, FAILED
    progress_message: Optional[str] = None
    sampling_step: Optional[int] = None
    sampling_total: Optional[int] = None
    product_id: str
    product_name: str
    variant_id: Optional[str] = None
    garment_type: str
    provider: str
    is_demo: bool = False
    disclaimer: str = "AI-generated visual preview. Actual fit, color and appearance may vary."
    preview_image_url: Optional[str] = None
    original_product_image_url: str
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    expires_at: datetime
    complete_the_look: List[StyleRecommendationItem] = []

class TryOnAnalyticsEventRequest(BaseModel):
    job_id: Optional[str] = None
    product_id: str
    event_type: str  # OPENED, UPLOADED, STARTED, COMPLETED, FAILED, CANCELLED, ADD_TO_CART, COMPARE_PRICES
    category: Optional[str] = None
    latency_ms: Optional[int] = None

class MerchantVTOReadinessItem(BaseModel):
    product_id: str
    name: str
    brand: Optional[str] = None
    category: str
    subcategory: Optional[str] = None
    image_url: Optional[str] = None
    vto_status: str  # READY, UNSUPPORTED_CATEGORY, MISSING_IMAGE
    garment_type: Optional[str] = None

class MerchantVTOStatsResponse(BaseModel):
    total_products: int
    vto_eligible_products: int
    vto_readiness_percentage: float
    total_tryons_started: int
    total_tryons_completed: int
    completion_rate_percentage: float
    add_to_cart_after_tryon_count: int
    items: List[MerchantVTOReadinessItem] = []
