from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from app.database.session import get_db
from app.database.models.merchant import Merchant
from app.database.models.purchase_intent import PurchaseIntent
from app.database.models.policy_evaluation import PolicyEvaluation
from app.database.models.user import User
from app.auth.deps import get_optional_current_user
from app.schemas.commerce import PurchaseIntentCreate, PurchaseIntentResponse
from app.schemas.policy import PolicyEvaluationResponse
from app.services.purchase_intent_service import PurchaseIntentService
from app.policies.policy_engine import PolicyEngine

router = APIRouter()

def _enforce_customer_only(current_user: Optional[User]) -> None:
    if current_user and current_user.role == "merchant_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Merchant accounts cannot create customer purchase intents."
        )

def _enforce_merchant_only(current_user: Optional[User]) -> None:
    if current_user and current_user.role != "merchant_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customer accounts cannot access merchant purchase intent dashboards."
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

@router.post("/", response_model=PurchaseIntentResponse)
def create_purchase_intent(
    payload: PurchaseIntentCreate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Creates a server-calculated, structured Purchase Intent.
    Validates cart, products, inventory, currency, and buyer constraints.
    Initial status: CREATED.
    """
    _enforce_customer_only(current_user)
    merchant = _resolve_merchant(db, payload.merchant_id)
    intent = PurchaseIntentService.create_purchase_intent(
        db=db,
        merchant_id=merchant.id,
        session_id=payload.session_id,
        buyer_id=payload.buyer_id,
        constraints=payload.constraints,
        delivery_address=payload.delivery_address,
        coupon_code=payload.coupon_code,
        voucher_code=payload.voucher_code,
        use_coins=payload.use_coins,
        coins_to_redeem=payload.coins_to_redeem,
        trace_id=payload.trace_id
    )
    return PurchaseIntentService.format_response(intent)

@router.post("/{id}/evaluate")
def evaluate_purchase_intent(
    id: str,
    merchant_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Evaluates a Purchase Intent against the merchant's deterministic policy rules.
    Decisions: ALLOW (generates TransactionAuthorization), REQUIRES_APPROVAL (generates ApprovalRequest), or DENY.
    """
    merchant = _resolve_merchant(db, merchant_id)
    result = PolicyEngine.evaluate_purchase_intent(
        db=db,
        purchase_intent_id=id,
        merchant_id=merchant.id,
        agent_id=agent_id,
        trace_id=trace_id
    )
    return result

@router.get("/{id}/evaluations")
def get_purchase_intent_evaluations(
    id: str,
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Retrieves historical policy evaluations for a purchase intent.
    """
    _enforce_merchant_only(current_user)
    merchant = _resolve_merchant(db, merchant_id)
    evals = db.query(PolicyEvaluation).filter(
        PolicyEvaluation.purchase_intent_id == id,
        PolicyEvaluation.merchant_id == merchant.id
    ).order_by(PolicyEvaluation.evaluated_at.desc()).all()

    return [PolicyEngine._format_evaluation_result(e) for e in evals]

@router.get("/{id}", response_model=PurchaseIntentResponse)
def get_purchase_intent(
    id: str,
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Retrieves purchase intent with automatic expiration check.
    """
    intent = PurchaseIntentService.get_purchase_intent_with_expiration(
        db=db,
        intent_id=id,
        merchant_id=merchant_id
    )
    return PurchaseIntentService.format_response(intent)

@router.get("/", response_model=List[PurchaseIntentResponse])
def list_purchase_intents(
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Lists all purchase intents for a merchant. Auto-expires outdated intents on retrieval.
    """
    _enforce_merchant_only(current_user)
    merchant = _resolve_merchant(db, merchant_id)
    intents = db.query(PurchaseIntent).filter(
        PurchaseIntent.merchant_id == merchant.id
    ).order_by(PurchaseIntent.created_at.desc()).all()

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    results = []
    
    for intent in intents:
        if intent.expires_at and now > intent.expires_at and intent.status in ("CREATED", "DRAFT", "VALIDATED"):
            intent.status = "EXPIRED"
            db.commit()
            db.refresh(intent)
        results.append(PurchaseIntentService.format_response(intent))

    return results
