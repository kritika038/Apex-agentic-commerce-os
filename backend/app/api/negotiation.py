"""
Negotiation API Router.
Endpoints for buyer <-> merchant agent price negotiations, merchant policy management,
approval workflows, offer lifecycle, and payment checkout.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case
from sqlalchemy.orm import Session
import logging

from app.database.session import get_db
from app.database.models.user import User
from app.database.models.merchant import Merchant
from app.database.models.product import Product
from app.database.models.negotiated_offer import NegotiatedOffer
from app.database.models.negotiation_policy import MerchantNegotiationPolicy
from app.auth.deps import get_current_user, get_optional_current_user
from app.negotiation.engine import NegotiationEngine
from app.negotiation.state_machine import NegotiationState
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


@router.get("/my-requests", response_model=List[NegotiatedOfferResponse])
def get_my_price_requests(
    status_filter: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieves authenticated customer's own negotiated price requests.
    Strictly isolated to the current user.
    """
    identifiers = [str(current_user.id)]
    if current_user.email:
        identifiers.append(current_user.email)
        identifiers.append(current_user.email.lower())

    query = db.query(NegotiatedOffer).filter(NegotiatedOffer.buyer_user_id.in_(identifiers))
    if status_filter:
        query = query.filter(NegotiatedOffer.status == status_filter)

    offers = query.order_by(NegotiatedOffer.created_at.desc()).all()
    return offers


@router.get("/my-requests/badge", response_model=Dict[str, int])
def get_my_price_requests_badge(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns actionable and total count of price requests for authenticated customer.
    """
    identifiers = [str(current_user.id)]
    if current_user.email:
        identifiers.append(current_user.email)
        identifiers.append(current_user.email.lower())

    offers = db.query(NegotiatedOffer).filter(NegotiatedOffer.buyer_user_id.in_(identifiers)).all()
    actionable_count = sum(1 for o in offers if o.is_actionable)
    return {
        "actionable_count": actionable_count,
        "total_count": len(offers),
    }


@router.get("/merchant-requests", response_model=List[NegotiatedOfferResponse])
def get_merchant_price_requests(
    status_filter: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieves customer price requests for authenticated merchant admin's tenant.
    Enforces merchant_admin role, tenant isolation, deterministic server-side sorting,
    and actionable filtering when requested.
    """
    if current_user.role not in ["merchant_admin", "admin"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Merchant admin access required.")

    m_id = current_user.merchant_id or "merch_default"
    query = db.query(NegotiatedOffer).filter(NegotiatedOffer.merchant_id == m_id)

    now_utc = datetime.now(timezone.utc)
    now_naive = now_utc.replace(tzinfo=None)

    if status_filter:
        s_upper = status_filter.upper()
        if s_upper in ["PENDING", "ACTIONABLE"]:
            query = query.filter(
                NegotiatedOffer.status.in_([
                    "HUMAN_APPROVAL_REQUIRED",
                    "WAITING_FOR_MERCHANT",
                    "OFFER_REQUESTED",
                    "NEGOTIATION_STARTED",
                    "MERCHANT_POLICY_EVALUATING",
                    "PENDING",
                ]),
                (NegotiatedOffer.expires_at == None) | (NegotiatedOffer.expires_at > now_naive)
            )
        elif s_upper == "APPROVED":
            query = query.filter(
                NegotiatedOffer.status.in_([
                    "MERCHANT_APPROVED",
                    "AUTO_ACCEPTED",
                    "CUSTOMER_OFFER_PRESENTED",
                ])
            )
        elif s_upper in ["COUNTERED", "COUNTER_OFFERED"]:
            query = query.filter(
                NegotiatedOffer.status.in_([
                    "COUNTER_OFFERED",
                    "MERCHANT_COUNTERED",
                ])
            )
        elif s_upper in ["DECLINED", "REJECTED"]:
            query = query.filter(
                NegotiatedOffer.status.in_([
                    "REJECTED",
                    "MERCHANT_REJECTED",
                    "CUSTOMER_REJECTED",
                ])
            )
        elif s_upper in ["CONFIRMED", "ORDER_CONFIRMED"]:
            query = query.filter(
                (NegotiatedOffer.status == "ORDER_CONFIRMED") | (NegotiatedOffer.payment_order_id != None)
            )
        elif s_upper == "EXPIRED":
            query = query.filter(
                (NegotiatedOffer.status == "EXPIRED") | (NegotiatedOffer.expires_at <= now_naive)
            )
        elif s_upper != "ALL":
            query = query.filter(NegotiatedOffer.status == status_filter)

    # Server-side authoritative sorting:
    # Priority 1: Counter-offers (active / not expired)
    # Priority 2: Pending / Actionable (active / not expired)
    # Priority 3: All others
    # Secondary order: created_at.desc()
    priority_order = case(
        (
            (NegotiatedOffer.status.in_(["COUNTER_OFFERED", "MERCHANT_COUNTERED"])) &
            ((NegotiatedOffer.expires_at == None) | (NegotiatedOffer.expires_at > now_naive)),
            1
        ),
        (
            (NegotiatedOffer.status.in_([
                "HUMAN_APPROVAL_REQUIRED",
                "WAITING_FOR_MERCHANT",
                "OFFER_REQUESTED",
                "NEGOTIATION_STARTED",
                "MERCHANT_POLICY_EVALUATING",
                "PENDING"
            ])) &
            ((NegotiatedOffer.expires_at == None) | (NegotiatedOffer.expires_at > now_naive)),
            2
        ),
        else_=3
    )

    offers = query.order_by(priority_order.asc(), NegotiatedOffer.created_at.desc()).limit(200).all()
    return offers


@router.get("/merchant-requests/badge", response_model=Dict[str, int])
def get_merchant_price_requests_badge(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns pending count (active non-expired requests awaiting merchant decision) and total count for merchant admin.
    """
    if current_user.role not in ["merchant_admin", "admin"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Merchant admin access required.")

    m_id = current_user.merchant_id or "merch_default"
    offers = db.query(NegotiatedOffer).filter(NegotiatedOffer.merchant_id == m_id).all()

    now_utc = datetime.now(timezone.utc)
    actionable_statuses = {
        "HUMAN_APPROVAL_REQUIRED",
        "WAITING_FOR_MERCHANT",
        "OFFER_REQUESTED",
        "NEGOTIATION_STARTED",
        "MERCHANT_POLICY_EVALUATING",
        "PENDING",
    }

    pending_count = 0
    for o in offers:
        if o.status in actionable_statuses:
            if o.expires_at:
                exp = o.expires_at if o.expires_at.tzinfo else o.expires_at.replace(tzinfo=timezone.utc)
                if exp > now_utc:
                    pending_count += 1
            else:
                pending_count += 1

    return {
        "pending_count": pending_count,
        "total_count": len(offers),
    }


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
    current_user: User = Depends(get_current_user),
):
    """Merchant approves an offer requiring human approval."""
    if current_user.role not in ["merchant_admin", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Merchant Admin privileges required."
        )
    m_id = _resolve_merchant_id(current_user, db, request.merchant_id)
    if current_user.merchant_id and current_user.merchant_id != m_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Merchant tenant mismatch."
        )
    try:
        offer = NegotiationEngine.merchant_approve(
            db=db,
            offer_id=offer_id,
            merchant_id=m_id,
            admin_user_id=current_user.id,
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
    current_user: User = Depends(get_current_user),
):
    """Merchant provides a custom counter-offer to buyer."""
    if current_user.role not in ["merchant_admin", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Merchant Admin privileges required."
        )
    m_id = _resolve_merchant_id(current_user, db, request.merchant_id)
    if current_user.merchant_id and current_user.merchant_id != m_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Merchant tenant mismatch."
        )
    try:
        offer = NegotiationEngine.merchant_counter(
            db=db,
            offer_id=offer_id,
            merchant_id=m_id,
            admin_user_id=current_user.id,
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
    current_user: User = Depends(get_current_user),
):
    """Merchant rejects negotiation proposal."""
    if current_user.role not in ["merchant_admin", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Merchant Admin privileges required."
        )
    m_id = _resolve_merchant_id(current_user, db, request.merchant_id)
    if current_user.merchant_id and current_user.merchant_id != m_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Merchant tenant mismatch."
        )
    try:
        offer = NegotiationEngine.merchant_reject(
            db=db,
            offer_id=offer_id,
            merchant_id=m_id,
            admin_user_id=current_user.id,
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


@router.get("/{offer_id}/validate-pdp", response_model=Dict[str, Any])
def validate_offer_for_pdp(
    offer_id: str,
    product_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Validates a negotiated offer for display and checkout on the Product Detail Page (PDP).
    Guarantees server-authoritative pricing, ownership check, stock availability,
    and expiration verification without trusting client-side query parameters.
    """
    offer = db.query(NegotiatedOffer).filter(
        (NegotiatedOffer.id == offer_id) | (NegotiatedOffer.negotiation_id == offer_id)
    ).first()

    if not offer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Negotiated price request not found."
        )

    # 1. Validate product match
    if product_id and offer.product_id != product_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product mismatch: This price request belongs to a different product."
        )

    # 2. Authorization / Ownership check
    if current_user and current_user.role not in ["merchant_admin", "admin"]:
        user_id_or_email = current_user.email or current_user.id
        if not NegotiationEngine._matches_buyer(db, offer.buyer_user_id, user_id_or_email):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You do not have permission to view this price request."
            )

    # 3. Expiration Check
    now_utc = datetime.now(timezone.utc)
    if offer.expires_at:
        exp = offer.expires_at if offer.expires_at.tzinfo else offer.expires_at.replace(tzinfo=timezone.utc)
        is_expired = (exp < now_utc) or (offer.status == NegotiationState.EXPIRED.value)
    else:
        is_expired = False
        exp = now_utc

    if is_expired and offer.status in [
        NegotiationState.COUNTER_OFFERED.value,
        NegotiationState.AUTO_ACCEPTED.value,
        NegotiationState.MERCHANT_APPROVED.value,
        NegotiationState.CUSTOMER_OFFER_PRESENTED.value,
        NegotiationState.HUMAN_APPROVAL_REQUIRED.value,
    ]:
        offer.status = NegotiationState.EXPIRED.value
        db.commit()

    # 4. Fetch Product and Check Inventory
    product = db.query(Product).filter(Product.id == offer.product_id).first()
    stock_qty = product.inventory.stock_quantity if (product and product.inventory) else (10 if product else 0)
    in_stock = bool(product and stock_qty >= offer.quantity)

    # 5. Determine State Flags
    is_counter = (offer.status in [NegotiationState.COUNTER_OFFERED.value, NegotiationState.MERCHANT_COUNTERED.value]) and not is_expired
    is_approved = (offer.status in [NegotiationState.AUTO_ACCEPTED.value, NegotiationState.MERCHANT_APPROVED.value]) and not is_expired
    is_accepted = (offer.status == NegotiationState.CUSTOMER_ACCEPTED.value) and not is_expired
    is_pending = (offer.status in [
        NegotiationState.HUMAN_APPROVAL_REQUIRED.value,
        NegotiationState.OFFER_REQUESTED.value,
        NegotiationState.NEGOTIATION_STARTED.value,
        NegotiationState.MERCHANT_POLICY_EVALUATING.value,
    ]) and not is_expired
    is_declined = offer.status in [
        NegotiationState.REJECTED.value,
        NegotiationState.CUSTOMER_REJECTED.value,
        NegotiationState.MERCHANT_REJECTED.value,
    ]
    is_confirmed = (offer.status == NegotiationState.ORDER_CONFIRMED.value) or (offer.payment_status == "CAPTURED")

    is_payable = (
        (is_approved or is_accepted or is_counter)
        and not is_expired
        and not is_confirmed
        and not is_declined
        and in_stock
    )

    seconds_remaining = max(0, int((exp - now_utc).total_seconds())) if not is_expired else 0

    return {
        "offer_id": offer.id,
        "offer_code": offer.offer_code,
        "product_id": offer.product_id,
        "product_name": product.name if product else (offer.product_name or "Product"),
        "product_image_url": product.image_url if product else offer.product_image_url,
        "quantity": offer.quantity,
        "list_price": float(offer.list_price),
        "list_total": float(offer.list_total),
        "requested_total": float(offer.requested_total),
        "offered_unit_price": float(offer.offered_unit_price),
        "final_total": float(offer.final_total),
        "discount_amount": float(offer.discount_amount),
        "discount_percent": float(offer.discount_percent),
        "currency": offer.currency,
        "status": offer.status,
        "reason": offer.merchant_message or offer.reason,
        "expires_at": offer.expires_at.isoformat() if offer.expires_at else "",
        "seconds_remaining": seconds_remaining,
        "is_expired": is_expired,
        "is_payable": is_payable,
        "is_counter": is_counter,
        "is_approved": is_approved,
        "is_accepted": is_accepted,
        "is_pending": is_pending,
        "is_declined": is_declined,
        "is_confirmed": is_confirmed,
        "in_stock": in_stock,
        "stock_quantity": stock_qty,
    }

