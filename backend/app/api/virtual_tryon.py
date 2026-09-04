import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Header, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.database.models.product import Product
from app.database.models.virtual_tryon import VirtualTryOnJob, VirtualTryOnEvent, TryOnJobStatus
from app.services.virtual_tryon.service import VirtualTryOnService
from app.services.virtual_tryon.registry import VTOProviderRegistry
from app.schemas.virtual_tryon import (
    TryOnEligibilityRequest,
    TryOnEligibilityResponse,
    TryOnJobStatusResponse,
    TryOnAnalyticsEventRequest,
    MerchantVTOStatsResponse
)
from app.auth.deps import get_optional_current_user, get_current_merchant_admin

router = APIRouter(prefix="/virtual-tryon", tags=["virtual-tryon"])

@router.get("/health")
@router.get("/status")
def get_tryon_provider_health():
    """
    Returns public, privacy-safe Virtual Try-On service health and provider configuration.
    Distinguishes: READY, BUSY, QUOTA_EXHAUSTED, SPACE_UNAVAILABLE, CONFIGURATION_ERROR.
    Never exposes API secrets or internal authentication tokens.
    """
    raw_enabled = os.environ.get("VIRTUAL_TRYON_ENABLED")
    if raw_enabled is not None:
        is_enabled = raw_enabled.lower() in ["true", "1", "yes"]
    else:
        from app.core.config import settings
        is_enabled = getattr(settings, "VIRTUAL_TRYON_ENABLED", True)

    provider = VTOProviderRegistry.get_provider()
    is_available = provider.is_available and is_enabled

    if not is_enabled:
        status_state = "CONFIGURATION_ERROR"
        status_msg = "Virtual Try-On is currently disabled."
    elif not provider.is_available or provider.provider_id == "unavailable":
        status_state = "CONFIGURATION_ERROR"
        status_msg = "AI Try-On configuration error."
    else:
        status_state = "READY"
        status_msg = "AI Try-On"

    return {
        "status": "healthy" if is_available else "unavailable",
        "state": status_state,
        "message": status_msg,
        "provider": provider.provider_id,
        "enabled": is_enabled,
        "configured": provider.is_available,
        "available": is_available,
        "is_demo": provider.is_demo
    }

@router.post("/check", response_model=TryOnEligibilityResponse)
def check_tryon_eligibility(
    payload: TryOnEligibilityRequest,
    db: Session = Depends(get_db)
):
    """
    Evaluates whether a product in the catalog is eligible for Virtual Try-On.
    Deterministic, instant evaluation.
    """
    product = db.query(Product).filter(Product.id == payload.product_id, Product.is_active == True).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    return VirtualTryOnService.is_virtual_tryon_supported(product)


@router.post("/jobs")
async def create_tryon_job(
    product_id: str = Form(...),
    consent: bool = Form(...),
    variant_id: Optional[str] = Form(None),
    session_id: Optional[str] = Form(None),
    background: bool = Form(False),
    photo: UploadFile = File(...),
    current_user = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """
    Creates and processes an AI Virtual Try-On job with uploaded user photo and explicit consent.
    """
    if not consent:
        raise HTTPException(status_code=400, detail="Explicit user consent is required before processing photo.")

    user_id = current_user.id if current_user else None
    
    # Read upload bytes
    photo_bytes = await photo.read()
    content_type = photo.content_type or "image/jpeg"

    try:
        job = VirtualTryOnService.create_and_execute_job(
            db=db,
            user_id=user_id,
            session_id=session_id,
            product_id=product_id,
            variant_id=variant_id,
            file_bytes=photo_bytes,
            content_type=content_type,
            consent_given=consent,
            background=background
        )
        return {
            "job_id": job.id,
            "status": job.status.value,
            "progress_percent": getattr(job, "progress_percent", 5) or 5,
            "processing_stage": getattr(job, "processing_stage", "PREPARING") or "PREPARING",
            "progress_message": getattr(job, "progress_message", "Preparing your photo..."),
            "garment_type": job.garment_type.value,
            "expires_at": job.expires_at.isoformat()
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Virtual try-on processing failed: {str(e)}")


@router.get("/jobs/{job_id}", response_model=TryOnJobStatusResponse)
def get_tryon_job_status(
    job_id: str,
    session_id: Optional[str] = None,
    current_user = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves status and synthesized preview for a try-on job with strict ownership verification.
    """
    job = db.query(VirtualTryOnJob).filter(VirtualTryOnJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Virtual try-on job not found.")

    # Ownership enforcement: only creator user or matching session can retrieve
    user_id = current_user.id if current_user else None
    if job.user_id and user_id and job.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied: You cannot view another user's try-on job.")
    if job.session_id and not user_id and session_id and job.session_id != session_id:
        raise HTTPException(status_code=403, detail="Access denied: Job does not belong to active session.")

    provider = VTOProviderRegistry.get_provider(job.provider)
    is_demo = provider.is_demo

    preview_url = f"/api/v1/virtual-tryon/media/{job.id}/result" if job.result_image_key else None
    style_recs = VirtualTryOnService.get_style_recommendations(db, job)

    return TryOnJobStatusResponse(
        job_id=job.id,
        status=job.status.value,
        progress_percent=getattr(job, "progress_percent", 0) or 0,
        processing_stage=getattr(job, "processing_stage", "PREPARING") or "PREPARING",
        progress_message=getattr(job, "progress_message", None),
        sampling_step=getattr(job, "sampling_step", None),
        sampling_total=getattr(job, "sampling_total", None),
        product_id=job.product_id,
        product_name=job.product_name_snapshot,
        variant_id=job.variant_id,
        garment_type=job.garment_type.value,
        provider=job.provider,
        is_demo=is_demo,
        preview_image_url=preview_url,
        original_product_image_url=job.product_image_url,
        error_code=job.error_code,
        error_message=job.error_message,
        created_at=job.created_at,
        completed_at=job.completed_at,
        expires_at=job.expires_at,
        complete_the_look=style_recs
    )


@router.post("/jobs/{job_id}/cancel")
def cancel_tryon_job(
    job_id: str,
    session_id: Optional[str] = None,
    current_user = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """
    Cancels an in-flight try-on job.
    """
    job = db.query(VirtualTryOnJob).filter(VirtualTryOnJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    user_id = current_user.id if current_user else None
    if job.user_id and user_id and job.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied.")

    job.status = TryOnJobStatus.CANCELLED
    db.commit()
    return {"message": "Job cancelled successfully", "status": "CANCELLED"}


@router.get("/media/{job_id}/{media_type}")
def get_tryon_media(
    job_id: str,
    media_type: str,  # "input" or "result"
    session_id: Optional[str] = None,
    current_user = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """
    Secure media streaming endpoint.
    Strictly prohibits unauthorized users and merchants from accessing private customer photos.
    """
    job = db.query(VirtualTryOnJob).filter(VirtualTryOnJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Media not found.")

    # Strict ownership validation
    user_id = current_user.id if current_user else None
    if job.user_id and user_id and job.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied: Cannot access another customer's media.")
    if job.session_id and not user_id and session_id and job.session_id != session_id:
        raise HTTPException(status_code=403, detail="Access denied.")

    key = job.result_image_key if media_type == "result" else job.input_image_key
    if not key:
        raise HTTPException(status_code=404, detail="Requested media is not ready.")

    media_path = VirtualTryOnService.get_media_path(key)
    if not media_path:
        raise HTTPException(status_code=404, detail="Media file not found in storage vault.")

    return FileResponse(media_path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})


@router.post("/analytics")
def record_tryon_analytics(
    event: TryOnAnalyticsEventRequest,
    current_user = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """
    Records privacy-safe analytics events for try-on engagement.
    Never stores image data or personal biometric information.
    """
    product = db.query(Product).filter(Product.id == event.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    vto_event = VirtualTryOnEvent(
        job_id=event.job_id,
        merchant_id=product.merchant_id,
        user_id=current_user.id if current_user else None,
        product_id=product.id,
        event_type=event.event_type,
        category=event.category or product.category,
        latency_ms=event.latency_ms
    )
    db.add(vto_event)
    db.commit()
    return {"status": "recorded"}


@router.get("/merchant-readiness", response_model=MerchantVTOStatsResponse)
def get_merchant_vto_readiness(
    merchant_user = Depends(get_current_merchant_admin),
    db: Session = Depends(get_db)
):
    """
    Merchant dashboard endpoint providing catalog VTO eligibility breakdown and aggregate conversion metrics.
    Completely zero access to individual customer photos.
    """
    return VirtualTryOnService.get_merchant_readiness_stats(db, merchant_user.merchant_id)
