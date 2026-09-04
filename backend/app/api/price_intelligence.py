from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any

from app.database.session import get_db
from app.schemas.price_comparison import PriceComparisonResponse
from app.services.price_intelligence.canonical_service import CanonicalPriceIntelligenceService

router = APIRouter()

@router.get("/price-intelligence/product/{product_id}", response_model=PriceComparisonResponse)
def get_product_price_intelligence(
    product_id: str,
    variant_id: Optional[str] = Query(None),
    force_refresh: bool = Query(False),
    db: Session = Depends(get_db)
):
    """
    Buyhatke-style Canonical Product Intelligence Graph.
    Unifies physical product identity across verified retailer listings.
    """
    return CanonicalPriceIntelligenceService.get_canonical_comparison(
        db=db,
        product_id=product_id,
        variant_id=variant_id,
        force_refresh=force_refresh
    )
