from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

from app.database.session import get_db
from app.database.models.merchant import Merchant
from app.database.models.product import Product
from app.database.models.user import User
from app.auth.deps import get_optional_current_user
from app.services.personalization_service import PersonalizationService
from app.services.interaction_service import ProductInteractionService
from app.services.product_affinity_service import ProductAffinityService
from app.services.fit_service import FitIntelligenceService
from app.services.review_intelligence_service import ReviewIntelligenceService

router = APIRouter()

class InteractionRecordRequest(BaseModel):
    product_id: str
    event_type: str # PRODUCT_VIEW, SEARCH, ADD_TO_CART, PURCHASE, FIT_CHECK
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

@router.get("/home")
def get_personalized_home_feed(
    session_id: Optional[str] = None,
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Returns personalized homepage feed based on real customer interaction signals and cold-start fallback.
    """
    m = db.query(Merchant).first()
    target_merchant_id = merchant_id or (m.id if m else "")
    user_id = current_user.id if current_user else None

    return PersonalizationService.get_homepage_feed(
        db=db,
        merchant_id=target_merchant_id,
        user_id=user_id,
        session_id=session_id
    )

@router.post("/interactions")
def record_customer_interaction(
    payload: InteractionRecordRequest,
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Records customer interaction for personalization.
    """
    m = db.query(Merchant).first()
    target_merchant_id = merchant_id or (m.id if m else "")
    user_id = current_user.id if current_user else None

    interaction = ProductInteractionService.record_interaction(
        db=db,
        merchant_id=target_merchant_id,
        product_id=payload.product_id,
        event_type=payload.event_type,
        user_id=user_id,
        session_id=payload.session_id,
        metadata=payload.metadata
    )
    return {"status": "SUCCESS", "interaction_id": interaction.id}

@router.get("/products/{id}/bundles")
def get_product_bundles(
    id: str,
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Returns frequently bought together smart bundles for a given product.
    Guarantees server-authoritative valid numeric pricing and complete fields.
    """
    m = db.query(Merchant).first()
    target_merchant_id = merchant_id or (m.id if m else "")

    main_product = db.query(Product).filter(
        Product.id == id,
        Product.is_active == True
    ).first()

    if not main_product or not main_product.price:
        return []

    try:
        main_price = float(main_product.price)
        if main_price <= 0:
            return []
    except (ValueError, TypeError):
        return []

    bundles = ProductAffinityService.get_frequently_bought_together(
        db=db,
        product_id=id,
        merchant_id=target_merchant_id,
        limit=3
    )

    results = []
    for b in bundles:
        p = b.get("product")
        if not p or not p.is_active:
            continue
        try:
            target_price = float(p.price)
            if target_price <= 0:
                continue
        except (ValueError, TypeError):
            continue

        p_id = str(p.id)
        bundle_price = round(main_price + target_price, 2)
        stock = p.inventory.stock_quantity if p.inventory else 10

        results.append({
            "target_product_id": p_id,
            "target_product_name": p.name,
            "target_price": target_price,
            "product_id": p_id,
            "name": p.name,
            "category": p.category,
            "price": target_price,
            "bundle_price": bundle_price,
            "savings": 0.0,
            "image_url": p.image_url or ((p.attributes or {}).get("image_url") if isinstance(p.attributes, dict) else None),
            "confidence": float(b.get("confidence", 0.85)),
            "support": float(b.get("support", 0.05)),
            "co_purchase_count": int(b.get("co_purchase_count", 0)),
            "evidence": b.get("evidence", f"Complementary {p.category} match for {main_product.name}"),
            "in_stock": stock > 0,
            "stock_quantity": stock
        })

    return results

@router.get("/products/{id}/fit-recommendation")
def get_product_fit_recommendation(
    id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Returns responsible sizing recommendations based on verified reviews and buyer history.
    """
    user_id = current_user.id if current_user else None
    return FitIntelligenceService.get_fit_recommendation(
        db=db,
        product_id=id,
        user_id=user_id
    )

@router.get("/products/{id}/reviews/summary")
def get_product_reviews_summary(
    id: str,
    db: Session = Depends(get_db)
):
    """
    Returns grounded AI review summary with pros, cons, and sentiment themes.
    """
    return ReviewIntelligenceService.get_review_summary(
        db=db,
        product_id=id
    )
