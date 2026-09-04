from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

from app.database.session import get_db
from app.database.models.merchant import Merchant
from app.database.models.user import User
from app.auth.deps import get_optional_current_user, get_current_active_user
from app.services.customer_support_service import CustomerSupportService

router = APIRouter()

class SupportChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class CreateReturnRequest(BaseModel):
    order_id: str
    product_id: str
    reason: str

@router.post("/chat")
def support_chat(
    payload: SupportChatRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Handles customer support queries regarding orders, returns, and rewards.
    """
    user_id = current_user.id if current_user else None
    email = current_user.email if current_user else None

    return CustomerSupportService.handle_support_query(
        db=db,
        message=payload.message,
        user_id=user_id,
        email=email
    )

@router.get("/orders")
def get_support_orders(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Retrieves authenticated orders for tracking.
    """
    user_id = current_user.id if current_user else None
    email = current_user.email if current_user else None

    return CustomerSupportService.get_customer_orders(
        db=db,
        user_id=user_id,
        email=email
    )

@router.post("/returns")
def create_customer_return(
    payload: CreateReturnRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Creates a governed customer return request and records an audit event.
    """
    m = db.query(Merchant).first()
    merchant_id = m.id if m else ""

    ret = CustomerSupportService.create_return_request(
        db=db,
        merchant_id=merchant_id,
        user_id=current_user.id,
        order_id=payload.order_id,
        product_id=payload.product_id,
        reason=payload.reason
    )

    return {
        "status": "SUCCESS",
        "return_id": ret.id,
        "order_id": ret.order_id,
        "refund_amount": float(ret.refund_amount),
        "message": "Return request recorded. Our warehouse team will process pickup within 48 hours."
    }
