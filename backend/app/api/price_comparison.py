from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any

from app.database.session import get_db
from app.auth.deps import get_optional_current_user
from app.database.models.user import User
from app.schemas.price_comparison import (
    PriceComparisonCheckRequest,
    PriceComparisonResponse,
    PriceHistoryResponse,
    OutboundRedirectResponse
)
from app.services.price_comparison_service import PriceComparisonService

router = APIRouter()

@router.post("/price-comparison/check", response_model=PriceComparisonResponse)
def check_price_comparison(
    payload: PriceComparisonCheckRequest,
    db: Session = Depends(get_db)
):
    """
    Computes external price comparison across verified stores for an Apex product.
    Returns lowest verified price, price differences, match confidence, and source links.
    """
    return PriceComparisonService.get_product_price_comparison(
        db=db,
        product_id=payload.product_id,
        variant_id=payload.variant_id,
        force_refresh=payload.force_refresh
    )

@router.get("/price-comparison/{product_id}", response_model=PriceComparisonResponse)
def get_price_comparison(
    product_id: str,
    variant_id: Optional[str] = Query(None),
    force_refresh: bool = Query(False),
    db: Session = Depends(get_db)
):
    """
    Retrieves cached or live price comparison for an Apex product.
    """
    return PriceComparisonService.get_product_price_comparison(
        db=db,
        product_id=product_id,
        variant_id=variant_id,
        force_refresh=force_refresh
    )

@router.get("/price-comparison/{product_id}/history", response_model=PriceHistoryResponse)
def get_price_history(
    product_id: str,
    db: Session = Depends(get_db)
):
    """
    Returns authentic 7d, 30d, 90d price observation history for price trend charting.
    """
    return PriceComparisonService.get_price_history(db=db, product_id=product_id)

@router.get("/external-offers/{offer_id}/redirect")
def redirect_to_external_offer(
    offer_id: str,
    session_id: Optional[str] = Query(None),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Authoritative Outbound Destination Gateway.
    Validates domain against whitelist, records click analytics, and safely redirects.
    """
    client_ip = request.client.host if request and request.client else None
    user_agent = request.headers.get("user-agent") if request else None
    user_id = current_user.id if current_user else None

    result = PriceComparisonService.process_outbound_redirect(
        db=db,
        offer_id=offer_id,
        user_id=user_id,
        session_id=session_id,
        ip_address=client_ip,
        user_agent=user_agent
    )

    # Return 307 temporary redirect to safe external destination
    return RedirectResponse(url=result.target_url, status_code=307)

@router.get("/external-offers/{offer_id}/info", response_model=OutboundRedirectResponse)
def get_outbound_info(
    offer_id: str,
    session_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Returns validated outbound redirect metadata for JSON API clients.
    """
    user_id = current_user.id if current_user else None
    return PriceComparisonService.process_outbound_redirect(
        db=db,
        offer_id=offer_id,
        user_id=user_id,
        session_id=session_id
    )
