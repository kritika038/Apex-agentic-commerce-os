from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.database.models.policy import Policy
from app.database.models.merchant import Merchant
from app.database.models.user import User
from app.schemas.policy import PolicyCreate, PolicyUpdate, PolicyResponse
from app.auth.deps import get_current_user, get_optional_current_user
from app.policies.policy_engine import PolicyEngine

router = APIRouter(tags=["Policies"])

def _resolve_merchant_id(current_user: Optional[User], db: Session, merchant_id: Optional[str] = None) -> str:
    if current_user and current_user.role not in ["merchant_admin", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Merchant Admin privileges required."
        )
    if current_user and current_user.merchant_id:
        return current_user.merchant_id
    if merchant_id:
        m = db.query(Merchant).filter(Merchant.id == merchant_id).first()
        if m:
            return m.id
    m = db.query(Merchant).first()
    if m:
        return m.id
    raise HTTPException(status_code=400, detail="Merchant not found.")

@router.get("", response_model=PolicyResponse)
def get_active_policy(
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    m_id = _resolve_merchant_id(current_user, db, merchant_id)
    policy = PolicyEngine.get_or_create_default_policy(db, m_id)
    return policy

@router.get("/history", response_model=List[PolicyResponse])
def get_policy_history(
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    m_id = _resolve_merchant_id(current_user, db, merchant_id)
    policies = db.query(Policy).filter(
        Policy.merchant_id == m_id
    ).order_by(Policy.version.desc()).all()
    return policies

@router.post("", response_model=PolicyResponse)
def create_or_update_policy(
    payload: PolicyCreate,
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    m_id = current_user.merchant_id or _resolve_merchant_id(current_user, db, merchant_id)
    
    # Check existing active policy
    existing = db.query(Policy).filter(
        Policy.merchant_id == m_id,
        Policy.is_active == True
    ).order_by(Policy.version.desc()).first()

    next_version = 1
    if existing:
        next_version = existing.version + 1
        existing.is_active = False

    new_policy = Policy(
        merchant_id=m_id,
        name=payload.name,
        version=next_version,
        max_transaction_amount=Decimal(str(payload.max_transaction_amount)),
        approval_threshold=Decimal(str(payload.approval_threshold)),
        low_risk_limit=Decimal(str(payload.low_risk_limit)),
        max_discount_percent=Decimal(str(payload.max_discount_percent)),
        max_quantity=payload.max_quantity,
        allowed_currency=payload.allowed_currency.upper(),
        auto_approval_enabled=payload.auto_approval_enabled,
        authorization_expiration_minutes=payload.authorization_expiration_minutes,
        is_active=True,
        created_by_user_id=current_user.id
    )
    db.add(new_policy)
    db.commit()
    db.refresh(new_policy)
    return new_policy

@router.put("/{id}", response_model=PolicyResponse)
def update_policy(
    id: str,
    payload: PolicyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Creates a new immutable policy version, preserving the previous version for historical audit reproducibility.
    """
    old_policy = db.query(Policy).filter(Policy.id == id).first()
    if not old_policy:
        raise HTTPException(status_code=404, detail="Policy not found.")

    m_id = old_policy.merchant_id
    if current_user.merchant_id and current_user.merchant_id != m_id:
        raise HTTPException(status_code=403, detail="Not authorized to modify another merchant's policy.")

    # Deactivate current active policies
    active_policies = db.query(Policy).filter(Policy.merchant_id == m_id, Policy.is_active == True).all()
    for p in active_policies:
        p.is_active = False

    latest_version = db.query(Policy).filter(Policy.merchant_id == m_id).order_by(Policy.version.desc()).first()
    next_version = (latest_version.version + 1) if latest_version else 1

    new_policy = Policy(
        merchant_id=m_id,
        name=payload.name or old_policy.name,
        version=next_version,
        max_transaction_amount=Decimal(str(payload.max_transaction_amount)) if payload.max_transaction_amount is not None else old_policy.max_transaction_amount,
        approval_threshold=Decimal(str(payload.approval_threshold)) if payload.approval_threshold is not None else old_policy.approval_threshold,
        low_risk_limit=Decimal(str(payload.low_risk_limit)) if payload.low_risk_limit is not None else old_policy.low_risk_limit,
        max_discount_percent=Decimal(str(payload.max_discount_percent)) if payload.max_discount_percent is not None else old_policy.max_discount_percent,
        max_quantity=payload.max_quantity if payload.max_quantity is not None else old_policy.max_quantity,
        allowed_currency=(payload.allowed_currency or old_policy.allowed_currency).upper(),
        auto_approval_enabled=payload.auto_approval_enabled if payload.auto_approval_enabled is not None else old_policy.auto_approval_enabled,
        authorization_expiration_minutes=payload.authorization_expiration_minutes if payload.authorization_expiration_minutes is not None else old_policy.authorization_expiration_minutes,
        is_active=True,
        created_by_user_id=current_user.id
    )
    db.add(new_policy)
    db.commit()
    db.refresh(new_policy)
    return new_policy
