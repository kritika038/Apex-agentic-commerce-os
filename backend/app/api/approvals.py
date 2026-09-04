from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.database.models.merchant import Merchant
from app.database.models.user import User
from app.database.models.approval_request import ApprovalRequest
from app.database.models.purchase_intent import PurchaseIntent
from app.schemas.policy import ApprovalRequestResponse, ApprovalActionRequest
from app.auth.deps import get_current_user, get_optional_current_user
from app.services.approval_service import ApprovalService

router = APIRouter(tags=["Human Approvals"])

def _enforce_merchant_admin(current_user: Optional[User]) -> None:
    if not current_user or current_user.role not in ["merchant_admin", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Merchant Admin privileges required."
        )

def _resolve_merchant_id(current_user: Optional[User], db: Session, merchant_id: Optional[str] = None) -> str:
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

@router.get("", response_model=List[ApprovalRequestResponse])
def list_approvals(
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """Merchant-only queue of pending/historical transaction approvals."""
    _enforce_merchant_admin(current_user)
    m_id = _resolve_merchant_id(current_user, db, merchant_id)
    return ApprovalService.get_merchant_approvals(db, m_id)

@router.get("/{id}", response_model=ApprovalRequestResponse)
def get_approval(
    id: str,
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Retrieves a specific approval request.
    Allowed for:
    - Merchant Admins (for operations)
    - The Customer who owns the transaction (for checkout review)
    """
    m_id = _resolve_merchant_id(current_user, db, merchant_id)
    req = ApprovalService.get_approval_by_id(db, id, m_id)

    # Ownership / Permission check
    is_admin = bool(current_user and current_user.role in ["merchant_admin", "admin"])
    if not is_admin:
        intent = db.query(PurchaseIntent).filter(PurchaseIntent.id == req.purchase_intent_id).first()
        if not intent:
            raise HTTPException(status_code=404, detail="Approval request not found.")
        is_owner = bool(
            (current_user and intent.buyer_id in [current_user.id, current_user.email]) or
            (not current_user and intent.session_id)
        )
        if not is_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this approval request."
            )

    return req

@router.post("/{id}/approve")
def approve_request(
    id: str,
    payload: Optional[ApprovalActionRequest] = None,
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Authorizes a pending transaction.
    Allowed for:
    - The Customer authorizing their own high-value order during checkout.
    - Merchant Admins approving from the governance console.
    """
    m_id = _resolve_merchant_id(current_user, db, merchant_id)
    req = db.query(ApprovalRequest).filter(ApprovalRequest.id == id, ApprovalRequest.merchant_id == m_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Approval request not found.")

    is_admin = bool(current_user and current_user.role in ["merchant_admin", "admin"])
    if not is_admin:
        # Customer authorizing own transaction
        intent = db.query(PurchaseIntent).filter(PurchaseIntent.id == req.purchase_intent_id).first()
        if not intent:
            raise HTTPException(status_code=404, detail="Associated purchase intent not found.")
        is_owner = bool(
            (current_user and intent.buyer_id in [current_user.id, current_user.email]) or
            (not current_user and intent.session_id)
        )
        if not is_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to approve another user's transaction."
            )
        user_id = f"customer:{current_user.id if current_user else 'direct'}"
    else:
        user_id = current_user.id if current_user else "merchant_admin"

    notes = payload.reason if payload else ("Approved by customer at checkout" if not is_admin else "Approved by merchant admin")

    req, auth = ApprovalService.approve_request(
        db=db,
        approval_id=id,
        merchant_id=m_id,
        user_id=user_id,
        notes=notes
    )

    return {
        "message": "Human approval granted successfully. Transaction authorized for future settlement.",
        "approval": {
            "id": req.id,
            "status": req.status,
            "approved_at": req.approved_at.isoformat() if req.approved_at else None,
            "approved_by_user_id": req.approved_by_user_id
        },
        "authorization": {
            "id": auth.id,
            "status": auth.status,
            "authorized_amount": str(auth.authorized_amount),
            "currency": auth.currency,
            "authorized_by": auth.authorized_by,
            "expires_at": auth.expires_at.isoformat() if auth.expires_at else None
        }
    }

@router.post("/{id}/reject")
def reject_request(
    id: str,
    payload: Optional[ApprovalActionRequest] = None,
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Cancels/Rejects a pending transaction approval.
    Allowed for:
    - The Customer canceling their own approval modal.
    - Merchant Admins rejecting an operational transaction.
    """
    m_id = _resolve_merchant_id(current_user, db, merchant_id)
    req = db.query(ApprovalRequest).filter(ApprovalRequest.id == id, ApprovalRequest.merchant_id == m_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Approval request not found.")

    is_admin = bool(current_user and current_user.role in ["merchant_admin", "admin"])
    if not is_admin:
        intent = db.query(PurchaseIntent).filter(PurchaseIntent.id == req.purchase_intent_id).first()
        if not intent:
            raise HTTPException(status_code=404, detail="Associated purchase intent not found.")
        is_owner = bool(
            (current_user and intent.buyer_id in [current_user.id, current_user.email]) or
            (not current_user and intent.session_id)
        )
        if not is_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to cancel another user's transaction."
            )
        user_id = f"customer:{current_user.id if current_user else 'direct'}"
        reason = payload.reason if payload else "Cancelled by customer at checkout."
    else:
        user_id = current_user.id if current_user else "merchant_admin"
        reason = payload.reason if payload else "Rejected by merchant operator."

    req = ApprovalService.reject_request(
        db=db,
        approval_id=id,
        merchant_id=m_id,
        user_id=user_id,
        reason=reason
    )

    return {
        "message": "Approval request rejected. Purchase intent marked as REJECTED.",
        "approval": {
            "id": req.id,
            "status": req.status,
            "rejected_at": req.rejected_at.isoformat() if req.rejected_at else None,
            "reason": req.reason
        }
    }
