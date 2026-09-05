from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional

from app.database.session import get_db
from app.database.models.merchant import Merchant
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.cart import Cart, CartItem
from app.database.models.recommendation import Recommendation
from app.database.models.user import User
from app.auth.deps import get_optional_current_user
from app.schemas.ai import ChatRequest, ChatResponse
from app.schemas.commerce import (
    BuyerRequest,
    BuyerConstraints,
    RecommendationResponse,
    RecommendationStatsResponse,
    PurchaseIntentResponse,
    PurchaseIntentCreate
)
from app.schemas.ai_protocol import MerchantProductResponseMessage
from app.agents.shopping_agent import ShoppingAgent
from app.agents.sales_agent import SalesAgent
from app.tools.shopping_tools import add_to_cart, get_cart

router = APIRouter()

def _enforce_customer_only(current_user: Optional[User]) -> None:
    if current_user and current_user.role == "merchant_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Merchant accounts cannot perform customer storefront actions."
        )

def _resolve_merchant(db: Session, merchant_id: Optional[str] = None) -> Merchant:
    if merchant_id:
        merchant = db.query(Merchant).filter(Merchant.id == merchant_id).first()
        if not merchant:
            raise HTTPException(status_code=404, detail=f"Merchant with ID '{merchant_id}' not found.")
        return merchant
    merchant = db.query(Merchant).first()
    if not merchant:
        raise HTTPException(status_code=404, detail="No active merchant found.")
    return merchant

@router.post("/shopping", response_model=ChatResponse)
@router.post("/chat", response_model=ChatResponse)
def ai_shopping_endpoint(
    req: ChatRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    _enforce_customer_only(current_user)
    merchant = _resolve_merchant(db, req.merchant_id)
    agent = ShoppingAgent(
        db=db,
        merchant_id=merchant.id,
        session_id=req.session_id,
        trace_id=req.trace_id,
        user=current_user,
        delivery_address=req.delivery_address,
        applied_coupon=req.applied_coupon,
        applied_voucher=req.applied_voucher,
        use_coins=req.use_coins,
        product_id=req.product_id
    )
    
    try:
        response = agent.process_message(req.message)
        
        # Contextual Sales Agent recommendations only if explicitly requested
        recs = []
        lower_msg = req.message.lower()
        if any(w in lower_msg for w in ["accessory", "accessories", "bundle", "complementary", "what else", "add-on", "what goes with"]):
            sales_agent = SalesAgent(db=db, merchant_id=merchant.id, session_id=req.session_id)
            recs_objs = sales_agent.generate_recommendations(trace_id=agent.trace_id)
            recs = [r.model_dump() for r in recs_objs]
        
        return ChatResponse(
            session_id=response.session_id,
            message=response.message,
            reply=response.message,
            products=response.products,
            cart=response.cart,
            recommendations=recs,
            actions=response.actions,
            structured_intent=response.structured_intent,
            order_review=response.order_review,
            requires_approval=response.requires_approval,
            approval_details=response.approval_details,
            trace_id=agent.trace_id
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/buyer/request", response_model=MerchantProductResponseMessage)
def ai_buyer_request_endpoint(
    req: BuyerRequest,
    db: Session = Depends(get_db)
):
    """
    Structured AI-to-AI Shopping Endpoint:
    Processes buyer requirements, executes merchant search, checks sales opportunities,
    and returns structured protocol response without trusting buyer-supplied commerce facts.
    """
    merchant = _resolve_merchant(db, req.merchant_id)
    
    # 1. Shopping Agent processing
    agent = ShoppingAgent(db=db, merchant_id=merchant.id, session_id=req.session_id)
    chat_resp = agent.process_message(req.message)
    
    # 2. Contextual Sales Agent recommendations
    sales_agent = SalesAgent(db=db, merchant_id=merchant.id, session_id=req.session_id)
    recommendations = sales_agent.generate_recommendations()
    
    # 3. Retrieve authoritative cart state
    cart_state = get_cart(db=db, merchant_id=merchant.id, session_id=req.session_id)
    
    # 4. Determine constraint satisfaction
    satisfied = True
    if req.constraints and req.constraints.max_price is not None:
        if cart_state.get("total_amount", 0.0) > req.constraints.max_price:
            satisfied = False

    return MerchantProductResponseMessage(
        session_id=req.session_id,
        message=chat_resp.message,
        products=chat_resp.products,
        cart=cart_state,
        recommendations=recommendations,
        constraints_satisfied=satisfied
    )

# Static routes before dynamic parameterized routes
@router.get("/recommendations/stats/summary", response_model=RecommendationStatsResponse)
def get_recommendation_stats(
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    merchant = _resolve_merchant(db, merchant_id)
    
    all_recs = db.query(Recommendation).filter(
        Recommendation.merchant_id == merchant.id
    ).order_by(Recommendation.created_at.desc()).all()
    
    total = len(all_recs)
    accepted = sum(1 for r in all_recs if r.status == "ACCEPTED")
    rejected = sum(1 for r in all_recs if r.status == "REJECTED")
    acceptance_rate = round((accepted / total * 100), 1) if total > 0 else 0.0
    
    # Calculate real added value from accepted recommendations
    added_value = Decimal("0.00")
    for r in all_recs:
        if r.status == "ACCEPTED" and r.product:
            added_value += Decimal(str(r.product.price))

    recent_responses = []
    for r in all_recs[:10]:
        recent_responses.append(RecommendationResponse(
            id=r.id,
            type=r.type,
            recommended_product_id=r.recommended_product_id,
            product_name=r.product.name if r.product else "Unknown",
            product_price=Decimal(str(r.product.price)) if r.product else Decimal("0.00"),
            reason=r.reason,
            confidence=r.confidence,
            status=r.status,
            source_product_id=r.source_product_id,
            trace_id=r.trace_id,
            created_at=r.created_at
        ))

    return RecommendationStatsResponse(
        total_recommendations=total,
        accepted_count=accepted,
        rejected_count=rejected,
        acceptance_rate=acceptance_rate,
        additional_cart_value=added_value,
        recent_recommendations=recent_responses
    )

@router.get("/recommendations/session/{session_id}", response_model=List[RecommendationResponse])
def get_session_recommendations(
    session_id: str,
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    merchant = _resolve_merchant(db, merchant_id)
    recs = db.query(Recommendation).filter(
        Recommendation.session_id == session_id,
        Recommendation.merchant_id == merchant.id
    ).order_by(Recommendation.created_at.desc()).all()
    
    results = []
    for r in recs:
        results.append(RecommendationResponse(
            id=r.id,
            type=r.type,
            recommended_product_id=r.recommended_product_id,
            product_name=r.product.name if r.product else "Unknown",
            product_price=Decimal(str(r.product.price)) if r.product else Decimal("0.00"),
            reason=r.reason,
            confidence=r.confidence,
            status=r.status,
            source_product_id=r.source_product_id,
            trace_id=r.trace_id,
            created_at=r.created_at
        ))
    return results

@router.post("/recommendations", response_model=List[RecommendationResponse])
def trigger_recommendations(
    req: ChatRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    _enforce_customer_only(current_user)
    merchant = _resolve_merchant(db, req.merchant_id)
    sales_agent = SalesAgent(db=db, merchant_id=merchant.id, session_id=req.session_id)
    return sales_agent.generate_recommendations()

@router.get("/recommendations/{id}", response_model=RecommendationResponse)
def get_recommendation_by_id(
    id: str,
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Recommendation).filter(Recommendation.id == id)
    if merchant_id:
        query = query.filter(Recommendation.merchant_id == merchant_id)
    rec = query.first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found.")
        
    return RecommendationResponse(
        id=rec.id,
        type=rec.type,
        recommended_product_id=rec.recommended_product_id,
        product_name=rec.product.name if rec.product else "Unknown",
        product_price=Decimal(str(rec.product.price)) if rec.product else Decimal("0.00"),
        reason=rec.reason,
        confidence=rec.confidence,
        status=rec.status,
        source_product_id=rec.source_product_id,
        trace_id=rec.trace_id,
        created_at=rec.created_at
    )

@router.post("/recommendations/{id}/accept")
def accept_recommendation(
    id: str,
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Accepts a recommendation:
    1. Validates product status and inventory in database.
    2. Adds product to authoritative cart.
    3. Updates recommendation status to ACCEPTED.
    4. Returns updated cart and confirmation.
    """
    _enforce_customer_only(current_user)
    query = db.query(Recommendation).filter(Recommendation.id == id)
    if merchant_id:
        query = query.filter(Recommendation.merchant_id == merchant_id)
    rec = query.first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found.")

    # 1. Independent backend validation of product & inventory
    product = db.query(Product).filter(
        Product.id == rec.recommended_product_id,
        Product.merchant_id == rec.merchant_id
    ).first()
    
    if not product or not product.is_active:
        raise HTTPException(status_code=400, detail="Recommended product is no longer active.")
        
    inventory = db.query(Inventory).filter(
        Inventory.product_id == product.id,
        Inventory.merchant_id == rec.merchant_id
    ).first()
    
    if not inventory or inventory.stock_quantity < 1:
        raise HTTPException(status_code=400, detail="Recommended product is currently out of stock.")

    # 2. Add to cart using deterministic cart tool
    cart_result = add_to_cart(
        db=db,
        merchant_id=rec.merchant_id,
        session_id=rec.session_id,
        product_id=product.id,
        quantity=1
    )
    
    if "error" in cart_result:
        raise HTTPException(status_code=400, detail=cart_result["error"])

    # 3. Update recommendation status
    rec.status = "ACCEPTED"
    db.commit()
    db.refresh(rec)

    # 4. Fetch updated cart
    cart_state = get_cart(db=db, merchant_id=rec.merchant_id, session_id=rec.session_id)
    return {
        "success": True,
        "recommendation_id": rec.id,
        "status": rec.status,
        "cart": cart_state
    }

@router.post("/recommendations/{id}/reject")
def reject_recommendation(
    id: str,
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Recommendation).filter(Recommendation.id == id)
    if merchant_id:
        query = query.filter(Recommendation.merchant_id == merchant_id)
    rec = query.first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found.")
        
    rec.status = "REJECTED"
    db.commit()
    db.refresh(rec)
    return {
        "success": True,
        "recommendation_id": rec.id,
        "status": rec.status
    }

@router.post("/purchase-intents", response_model=PurchaseIntentResponse)
def create_ai_purchase_intent(
    payload: PurchaseIntentCreate,
    db: Session = Depends(get_db)
):
    """
    Structured Purchase Intent generation endpoint.
    Calculates amount strictly server-side from real database cart records.
    """
    from app.services.purchase_intent_service import PurchaseIntentService
    merchant = _resolve_merchant(db, payload.merchant_id)
    intent = PurchaseIntentService.create_purchase_intent(
        db=db,
        merchant_id=merchant.id,
        session_id=payload.session_id,
        buyer_id=payload.buyer_id,
        constraints=payload.constraints,
        trace_id=payload.trace_id
    )
    return PurchaseIntentService.format_response(intent)
