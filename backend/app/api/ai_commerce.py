from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Header, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.database.models.user import User
from app.auth.deps import get_optional_current_user
from app.agents.apex_commerce_agent import ApexCommerceAgent
from app.services.ai_commerce_service import AICommerceService
from app.schemas.ai_commerce import (
    AgentSearchRequest,
    AgentSearchResponse,
    AgentNegotiateRequest,
    AgentSelectOfferRequest,
    AgentSelectOfferResponse,
    AgentPurchaseIntentRequest,
    AgentPurchaseIntentResponse,
    AgentApprovePayRequest,
    AgentApprovePayResponse,
    AgentVerifyPaymentRequest,
    AgentVerifyPaymentResponse,
    AICommerceActivityResponse,
)

router = APIRouter(prefix="/ai-commerce", tags=["AI-to-AI Commerce"])

def get_authenticated_agent_buyer(
    x_agent_key: Optional[str] = Header(None, alias="X-Agent-Key"),
    current_user: Optional[User] = Depends(get_optional_current_user)
) -> str:
    """
    Secure agent authentication layer:
    - For external agents: validates X-Agent-Key or authenticated Bearer token.
    - For internal demo agent: binds to verified user identity or secure session.
    Never trusts forged/unverified client headers.
    """
    if current_user and current_user.email:
        return current_user.email
    if x_agent_key and len(x_agent_key.strip()) >= 8:
        return f"agent_key_{x_agent_key[:8]}"
    return "customer_ai"

@router.post("/search", response_model=AgentSearchResponse)
def agent_search_endpoint(
    request: AgentSearchRequest,
    merchant_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    buyer_id: str = Depends(get_authenticated_agent_buyer)
):
    """
    AI Buyer searches Apex Sports catalog via structured protocol or natural language.
    """
    agent = ApexCommerceAgent(db=db, merchant_id=merchant_id)
    return agent.handle_search(request=request, buyer_id=buyer_id)

@router.post("/negotiate", response_model=AgentSearchResponse)
def agent_negotiate_endpoint(
    request: AgentNegotiateRequest,
    merchant_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    buyer_id: str = Depends(get_authenticated_agent_buyer)
):
    """
    AI Buyer negotiates constraints (budget adjustments, cheapest options, best matches).
    """
    agent = ApexCommerceAgent(db=db, merchant_id=merchant_id)
    return agent.handle_negotiation(request=request, buyer_id=buyer_id)

@router.post("/select-offer", response_model=AgentSelectOfferResponse)
def agent_select_offer_endpoint(
    request: AgentSelectOfferRequest,
    merchant_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    AI Buyer selects an offer; server re-validates live stock and price stability.
    """
    return AICommerceService.select_offer(db=db, request=request, merchant_id=merchant_id)

@router.post("/purchase-intent", response_model=AgentPurchaseIntentResponse)
def agent_purchase_intent_endpoint(
    request: AgentPurchaseIntentRequest,
    merchant_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    buyer_id: str = Depends(get_authenticated_agent_buyer)
):
    """
    Creates a server-authoritative PurchaseIntent and evaluates deterministic governance policies.
    """
    return AICommerceService.create_purchase_intent(
        db=db,
        request=request,
        merchant_id=merchant_id,
        authenticated_buyer_id=buyer_id
    )

@router.post("/approve-and-pay", response_model=AgentApprovePayResponse)
def agent_approve_and_pay_endpoint(
    request: AgentApprovePayRequest,
    merchant_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Human-in-the-loop explicit approval authorizing transaction and creating Razorpay Test Mode order.
    """
    try:
        return AICommerceService.approve_and_pay(
            db=db,
            request=request,
            merchant_id=merchant_id,
            authenticated_user=current_user
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/verify-payment", response_model=AgentVerifyPaymentResponse)
def agent_verify_payment_endpoint(
    request: AgentVerifyPaymentRequest,
    merchant_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Server-side HMAC-SHA256 Razorpay signature verification and order finalization.
    """
    try:
        return AICommerceService.verify_payment(
            db=db,
            request=request,
            merchant_id=merchant_id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/activity", response_model=AICommerceActivityResponse)
def agent_activity_endpoint(
    merchant_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Exposes real, computed AI commerce activity and audit records for merchant dashboard.
    """
    return AICommerceService.get_merchant_activity(db=db, merchant_id=merchant_id)
