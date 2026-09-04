"""
Negotiation API Router.
Endpoints for buyer <-> merchant agent price negotiations, merchant policy management,
approval workflows, offer lifecycle, and payment checkout.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
import logging

from app.database.session import get_db
from app.database.models.user import User
from app.database.models.merchant import Merchant
from app.database.models.negotiated_offer import NegotiatedOffer
from app.database.models.negotiation_policy import MerchantNegotiationPolicy
from app.auth.deps import get_optional_current_user
from app.negotiation.engine import NegotiationEngine
from app.agents.merchant_negotiation_agent import MerchantNegotiationAgent
from app.schemas.negotiation import (
    NegotiationStartRequest,
    CustomerActionRequest,
    MerchantApproveRequest,
    MerchantCounterRequest,
    MerchantRejectRequest,
    NegotiationCheckoutRequest,
    NegotiatedOfferResponse,
    NegotiationPolicyUpdate,
    NegotiationPolicyResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/negotiation", tags=["Agentic Price Negotiation"])


def _resolve_merchant_id(current_user: Optional[User], db: Session, merchant_id: Optional[str] = None) -> str:
    if current_user and current_user.merchant_id:
        return current_user.merchant_id
    if merchant_id:
        return merchant_id
    m = db.query(Merchant).first()
    if m:
        return m.id
    return "merch_default"


def _resolve_customer_id(current_user: Optional[User], requested_customer_id: Optional[str] = None) -> str:
    if current_user and current_user.email:
        return current_user.email
    if requested_customer_id:
        return requested_customer_id
    return "cust_default"


@router.post("/start", response_model=Dict[str, Any])
def start_negotiation_endpoint(
    request: NegotiationStartRequest,
    merchant_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Start a negotiation for a product with quantity and requested price.
    Evaluates merchant policy deterministically and returns structured offer + agent response.
    """
    m_id = _resolve_merchant_id(current_user, db, merchant_id)
    cust_id = _resolve_customer_id(current_user, request.customer_id)

    agent = MerchantNegotiationAgent(db=db, merchant_id=m_id)
    try:
        result = agent.process_buyer_negotiation_request(
            product_id=request.product_id,
            quantity=request.quantity,
            requested_unit_price=request.requested_unit_price,
            requested_total=request.requested_total,
            customer_id=cust_id,
            buyer_agent_id=request.buyer_agent_id or "buyer-agent-standard",
            buyer_note=request.buyer_note,
        )
        offer_dict = NegotiatedOfferResponse.model_validate(result["offer"]).model_dump()
        return {
            "offer": offer_dict,
            "agent_message": result["agent_message"],
            "status": result["status"],
            "requires_action": result["requires_action"],
            "trace": result["trace"],
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.exception("Error in negotiation start")
        raise HTTPException(status_code=500, detail=f"Negotiation failed: {str(e)}")


@router.get("/policy", response_model=NegotiationPolicyResponse)
def get_policy_endpoint(
    merchant_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """Retrieves active merchant negotiation policy."""
    m_id = _resolve_merchant_id(current_user, db, merchant_id)
    policy = NegotiationEngine.get_or_create_merchant_policy(db=db, merchant_id=m_id)
    return policy


@router.put("/policy", response_model=NegotiationPolicyResponse)
def update_policy_endpoint(
    request: NegotiationPolicyUpdate,
    merchant_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """Updates merchant negotiation policy parameters."""
    m_id = _resolve_merchant_id(current_user, db, merchant_id)
    policy = NegotiationEngine.get_or_create_merchant_policy(db=db, merchant_id=m_id)

    update_data = request.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(policy, k, v)

    db.commit()
    db.refresh(policy)
    return policy


@router.get("/merchant/list", response_model=List[NegotiatedOfferResponse])
def list_merchant_negotiations(
    merchant_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """Lists negotiation offers for merchant dashboard."""
    m_id = _resolve_merchant_id(current_user, db, merchant_id)
    query = db.query(NegotiatedOffer).filter(NegotiatedOffer.merchant_id == m_id)
    if status_filter:
        query = query.filter(NegotiatedOffer.status == status_filter)
    offers = query.order_by(NegotiatedOffer.created_at.desc()).limit(100).all()
    return offers


@router.get("/{offer_id}", response_model=NegotiatedOfferResponse)
def get_negotiation_offer(
    offer_id: str,
    db: Session = Depends(get_db),
):
    """Retrieves offer status and details by offer ID or offer code."""
    offer = db.query(NegotiatedOffer).filter(
        (NegotiatedOffer.id == offer_id) | (NegotiatedOffer.negotiation_id == offer_id)
    ).first()

    if not offer:
        raise HTTPException(status_code=404, detail="Negotiated offer not found.")
    return offer


@router.post("/{offer_id}/accept", response_model=NegotiatedOfferResponse)
def customer_accept_offer(
    offer_id: str,
    request: CustomerActionRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """Customer accepts the negotiated or countered offer."""
    cust_id = _resolve_customer_id(current_user, request.customer_id)
    try:
        offer = NegotiationEngine.customer_accept_offer(
            db=db,
            offer_id=offer_id,
            customer_id=cust_id,
            reason=request.reason,
        )
        return offer
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.exception("Error accepting offer")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{offer_id}/reject", response_model=NegotiatedOfferResponse)
def customer_reject_offer(
    offer_id: str,
    request: CustomerActionRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """Customer rejects the counter-offer or terms."""
    cust_id = _resolve_customer_id(current_user, request.customer_id)
    try:
        offer = NegotiationEngine.customer_reject_offer(
            db=db,
            offer_id=offer_id,
            customer_id=cust_id,
            reason=request.reason,
        )
        return offer
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.exception("Error rejecting offer")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{offer_id}/merchant/approve", response_model=NegotiatedOfferResponse)
def merchant_approve_offer(
    offer_id: str,
    request: MerchantApproveRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """Merchant approves an offer requiring human approval."""
    m_id = _resolve_merchant_id(current_user, db, request.merchant_id)
    try:
        offer = NegotiationEngine.merchant_approve(
            db=db,
            offer_id=offer_id,
            merchant_id=m_id,
            approver_email=current_user.email if current_user else "merchant_admin@apex.local",
            reason=request.reason,
        )
        return offer
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.exception("Error merchant approving offer")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{offer_id}/merchant/counter", response_model=NegotiatedOfferResponse)
def merchant_counter_offer(
    offer_id: str,
    request: MerchantCounterRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """Merchant provides a custom counter-offer to buyer."""
    m_id = _resolve_merchant_id(current_user, db, request.merchant_id)
    try:
        offer = NegotiationEngine.merchant_counter(
            db=db,
            offer_id=offer_id,
            merchant_id=m_id,
            counter_unit_price=request.counter_unit_price,
            counter_total=request.counter_total,
            reason=request.reason,
        )
        return offer
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.exception("Error merchant counter offer")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{offer_id}/merchant/reject", response_model=NegotiatedOfferResponse)
def merchant_reject_offer(
    offer_id: str,
    request: MerchantRejectRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """Merchant rejects negotiation proposal."""
    m_id = _resolve_merchant_id(current_user, db, request.merchant_id)
    try:
        offer = NegotiationEngine.merchant_reject(
            db=db,
            offer_id=offer_id,
            merchant_id=m_id,
            reason=request.reason,
        )
        return offer
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.exception("Error merchant rejecting offer")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{offer_id}/checkout", response_model=Dict[str, Any])
def create_negotiation_checkout(
    offer_id: str,
    request: NegotiationCheckoutRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Creates Razorpay payment order locked strictly to the server-authoritative offer final_total.
    Prevents any client-side price tampering.
    """
    cust_id = _resolve_customer_id(current_user, request.customer_id)
    try:
        result = NegotiationEngine.create_payment_order_for_offer(
            db=db,
            offer_id=offer_id,
            customer_id=cust_id,
            payment_method=request.payment_method or "upi",
        )
        return result
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.exception("Error initiating checkout for negotiation")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{offer_id}/trace", response_model=Dict[str, Any])
def get_negotiation_trace(
    offer_id: str,
    db: Session = Depends(get_db),
):
    """Returns complete audit log and policy decision trace for the negotiation."""
    offer = db.query(NegotiatedOffer).filter(
        (NegotiatedOffer.id == offer_id) | (NegotiatedOffer.negotiation_id == offer_id)
    ).first()

    if not offer:
        raise HTTPException(status_code=404, detail="Negotiated offer not found.")

    return {
        "offer_id": offer.id,
        "offer_code": offer.offer_code,
        "status": offer.status,
        "audit_hash": offer.audit_hash,
        "created_at": offer.created_at.isoformat(),
        "expires_at": offer.expires_at.isoformat(),
        "pricing": {
            "list_unit_price": str(offer.list_unit_price),
            "requested_unit_price": str(offer.requested_unit_price),
            "offered_unit_price": str(offer.offered_unit_price),
            "final_total": str(offer.final_total),
            "discount_amount": str(offer.discount_amount),
            "discount_percent": str(offer.discount_percent),
            "currency": offer.currency,
        },
        "governance": {
            "approval_request_id": offer.approval_request_id,
            "transaction_authorization_id": offer.transaction_authorization_id,
            "requires_human_approval": offer.requires_human_approval,
            "customer_accepted": offer.customer_accepted,
        },
        "payment": {
            "payment_order_id": offer.payment_order_id,
            "payment_status": offer.payment_status,
            "order_id": offer.order_id,
        },
        "metadata": offer.metadata_json or {},
    }
