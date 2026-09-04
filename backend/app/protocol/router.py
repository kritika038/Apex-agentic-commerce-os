from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.database.models.user import User
from app.database.models.merchant import Merchant
from app.auth.deps import get_optional_current_user
from app.protocol.schemas import (
    ProtocolCapabilitiesResponse,
    ProtocolDiscoverRequest,
    ProtocolDiscoverResponse,
    ProtocolRecommendRequest,
    ProtocolRecommendResponse,
    ProtocolPurchaseIntentRequest,
    ProtocolPurchaseIntentResponse,
    ProtocolAuthorizationStatusResponse,
    ProtocolPaymentRequest,
    ProtocolPaymentResponse
)
from app.protocol.service import ProtocolService

router = APIRouter(prefix="/protocol", tags=["AI-to-AI Commerce Protocol"])

def _resolve_merchant(db: Session, merchant_id: Optional[str], current_user: Optional[User]) -> str:
    if current_user and current_user.merchant_id:
        return current_user.merchant_id
    if merchant_id:
        m = db.query(Merchant).filter(Merchant.id == merchant_id).first()
        if m:
            return m.id
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target merchant '{merchant_id}' not found."
        )
    # Default to active merchant in single-tenant/demo context
    m = db.query(Merchant).filter(Merchant.is_active == True).first()
    if m:
        return m.id
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Merchant context required. Provide merchant_id parameter or header."
    )

@router.get("/capabilities", response_model=ProtocolCapabilitiesResponse)
def get_protocol_capabilities(
    merchant_id: Optional[str] = Query(None, description="Optional merchant ID"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Machine-readable discovery of merchant operations, capabilities, supported currency,
    and security guarantees for external AI buyers and autonomous agents.
    """
    m_id = _resolve_merchant(db, merchant_id, current_user)
    return ProtocolService.get_capabilities(db=db, merchant_id=m_id)

@router.post("/discover", response_model=ProtocolDiscoverResponse)
def protocol_discover(
    payload: ProtocolDiscoverRequest,
    merchant_id: Optional[str] = Query(None, description="Optional merchant ID"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Autonomous product discovery matching structured constraints against authoritative catalog.
    Prices and stock quantities originate strictly from SQL database records.
    """
    m_id = _resolve_merchant(db, payload.merchant_id or merchant_id, current_user)
    return ProtocolService.discover(db=db, req=payload, merchant_id=m_id)

@router.post("/recommend", response_model=ProtocolRecommendResponse)
def protocol_recommend(
    payload: ProtocolRecommendRequest,
    merchant_id: Optional[str] = Query(None, description="Optional merchant ID"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Contextual recommendation protocol allowing merchant SalesAgent to propose
    grounded cross-sells and upsells to external AI buyers.
    """
    m_id = _resolve_merchant(db, payload.merchant_id or merchant_id, current_user)
    return ProtocolService.recommend(db=db, req=payload, merchant_id=m_id)

@router.post("/purchase-intent", response_model=ProtocolPurchaseIntentResponse)
def protocol_purchase_intent(
    payload: ProtocolPurchaseIntentRequest,
    merchant_id: Optional[str] = Query(None, description="Optional merchant ID"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Creates a server-validated Purchase Intent from an authoritative cart.
    Enforces stock, merchant ownership, and buyer budget constraints.
    NO payment charges occur here.
    """
    m_id = _resolve_merchant(db, payload.merchant_id or merchant_id, current_user)
    return ProtocolService.create_purchase_intent(db=db, req=payload, merchant_id=m_id)

@router.get("/authorization/{purchase_intent_id}", response_model=ProtocolAuthorizationStatusResponse)
def protocol_authorization_status(
    purchase_intent_id: str,
    merchant_id: Optional[str] = Query(None, description="Optional merchant ID"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Inspects current authorization lifecycle state for an external AI buyer:
    NOT_EVALUATED | AUTHORIZED | REQUIRES_APPROVAL | DENIED | EXPIRED
    """
    m_id = _resolve_merchant(db, merchant_id, current_user)
    return ProtocolService.get_authorization_status(db=db, purchase_intent_id=purchase_intent_id, merchant_id=m_id)

@router.post("/payment-request", response_model=ProtocolPaymentResponse)
def protocol_payment_request(
    payload: ProtocolPaymentRequest,
    merchant_id: Optional[str] = Query(None, description="Optional merchant ID"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Strict payment initiation boundary for authorized purchase intents.
    Amount and currency are derived exclusively from the TransactionAuthorization snapshot;
    client-supplied overrides are rejected.
    """
    m_id = _resolve_merchant(db, payload.merchant_id or merchant_id, current_user)
    return ProtocolService.request_payment(db=db, req=payload, merchant_id=m_id)
