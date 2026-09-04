from datetime import datetime, timezone
import enum
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SQLEnum, Text, Integer, Float, Boolean, JSON
from sqlalchemy.orm import relationship

from app.database.models.base import Base, generate_uuid

class TryOnGarmentType(str, enum.Enum):
    CLOTHING = "CLOTHING"
    FOOTWEAR = "FOOTWEAR"
    ACCESSORY = "ACCESSORY"

class TryOnJobStatus(str, enum.Enum):
    CREATED = "CREATED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"

class VirtualTryOnJob(Base):
    __tablename__ = "virtual_tryon_jobs"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    session_id = Column(String, nullable=True, index=True)
    product_id = Column(String, ForeignKey("products.id"), nullable=False, index=True)
    merchant_id = Column(String, ForeignKey("merchants.id"), nullable=False, index=True)
    variant_id = Column(String, nullable=True)
    garment_type = Column(SQLEnum(TryOnGarmentType), nullable=False)
    provider = Column(String, default="demo", nullable=False)
    status = Column(SQLEnum(TryOnJobStatus), default=TryOnJobStatus.CREATED, nullable=False, index=True)
    
    # Secure storage references (internal safe filenames, never exposed as raw paths)
    input_image_key = Column(String, nullable=False)
    result_image_key = Column(String, nullable=True)
    product_image_url = Column(String, nullable=False)
    
    # Metadata snapshot
    product_name_snapshot = Column(String, nullable=False)
    variant_metadata = Column(JSON, nullable=True)

    # Real Progress & Diffusion Sampling Lifecycle
    progress_percent = Column(Integer, default=0, nullable=False)
    processing_stage = Column(String, default="PREPARING", nullable=False)
    progress_message = Column(String, default="Preparing your photo...", nullable=True)
    sampling_step = Column(Integer, nullable=True)
    sampling_total = Column(Integer, nullable=True)
    
    # Error tracking
    error_code = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Timing
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)

    user = relationship("User", backref="virtual_tryon_jobs")
    product = relationship("Product", backref="virtual_tryon_jobs")

class VirtualTryOnEvent(Base):
    __tablename__ = "virtual_tryon_events"

    id = Column(String, primary_key=True, default=generate_uuid)
    job_id = Column(String, nullable=True, index=True)
    merchant_id = Column(String, ForeignKey("merchants.id"), nullable=False, index=True)
    user_id = Column(String, nullable=True)
    product_id = Column(String, nullable=False, index=True)
    event_type = Column(String, nullable=False)  # OPENED, UPLOADED, STARTED, COMPLETED, FAILED, CANCELLED, ADD_TO_CART, COMPARE_PRICES
    category = Column(String, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
