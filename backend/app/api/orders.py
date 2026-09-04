from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any

from app.database.session import get_db
from app.database.models.user import User
from app.auth.deps import get_current_user, get_optional_current_user
from app.schemas.order import (
    OrderResponse,
    BuyAgainRequest,
    BuyAgainResponse,
    OrderCancelRequest,
    OrderReturnRequest
)
from app.services.order_service import OrderService

router = APIRouter(tags=["Orders"])

@router.get("/me", response_model=List[OrderResponse])
def get_my_orders(
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves previous orders for the authenticated customer.
    Identity is derived strictly from the backend JWT token.
    """
    buyer_id = current_user.email or current_user.id
    return OrderService.get_customer_orders(db=db, buyer_id=buyer_id, limit=limit)

@router.get("/{id}", response_model=OrderResponse)
def get_order_details(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves details for a specific order.
    Customers may only view their own orders. Merchant admins may view any order.
    """
    is_admin = current_user.role == "merchant_admin"
    buyer_id = current_user.email or current_user.id
    return OrderService.get_order_by_id(
        db=db,
        order_id=id,
        buyer_id=buyer_id,
        is_admin=is_admin
    )

@router.post("/{id}/buy-again", response_model=BuyAgainResponse)
def buy_again_order_items(
    id: str,
    payload: BuyAgainRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Reorders items from a past order into the customer's current cart session.
    Applies current authoritative database pricing and real-time inventory checks.
    """
    is_admin = bool(current_user and current_user.role == "merchant_admin")
    buyer_id = current_user.email if current_user else None
    return OrderService.buy_again(
        db=db,
        order_id=id,
        session_id=payload.session_id,
        buyer_id=buyer_id,
        is_admin=is_admin
    )

@router.post("/{id}/cancel", response_model=Dict[str, Any])
def cancel_order(
    id: str,
    payload: Optional[OrderCancelRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Cancels an order and restocks inventory.
    """
    is_admin = current_user.role == "merchant_admin"
    buyer_id = current_user.email or current_user.id
    reason = payload.reason if payload else "Customer requested cancellation"
    return OrderService.cancel_order(
        db=db,
        order_id=id,
        buyer_id=buyer_id,
        reason=reason,
        is_admin=is_admin
    )

@router.post("/{id}/return", response_model=Dict[str, Any])
def return_order(
    id: str,
    payload: OrderReturnRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submits a return request for eligible items.
    """
    is_admin = current_user.role == "merchant_admin"
    buyer_id = current_user.email or current_user.id
    return OrderService.return_order(
        db=db,
        order_id=id,
        buyer_id=buyer_id,
        reason=payload.reason,
        quantity=payload.quantity or 1,
        is_admin=is_admin
    )

