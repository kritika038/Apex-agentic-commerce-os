import os
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database.session import get_db
from app.core.config import settings

router = APIRouter(tags=["Health & Readiness"])

@router.get("/health")
def health_check() -> Dict[str, Any]:
    """
    Liveness probe. Returns 200 OK if the web server process is responsive.
    Minimal output to prevent information leakage.
    """
    return {
        "status": "healthy",
        "service": "Agentic Commerce OS"
    }

@router.get("/ready")
def readiness_check(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Readiness probe. Verifies database connectivity and provider configuration state.
    Does not expose secrets, credentials, internal file paths, or connection strings.
    """
    db_status = "healthy"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unhealthy"

    provider_name = getattr(settings, "PAYMENT_PROVIDER", "mock")
    is_razorpay_configured = bool(
        getattr(settings, "RAZORPAY_KEY_ID", "") and 
        getattr(settings, "RAZORPAY_KEY_SECRET", "")
    )

    is_ready = db_status == "healthy"

    response_payload = {
        "status": "ready" if is_ready else "not_ready",
        "database": db_status,
        "payment_provider": {
            "configured_mode": provider_name,
            "credentials_present": is_razorpay_configured if provider_name == "razorpay" else True
        },
        "environment": getattr(settings, "ENVIRONMENT", "development")
    }

    if not is_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=response_payload
        )

    return response_payload
