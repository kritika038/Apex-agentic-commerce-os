from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.database.models.cart import Cart, CartItem
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.merchant import Merchant
from app.auth.deps import get_optional_current_user


router = APIRouter()


class CartItemAdd(BaseModel):
    product_id: str
    quantity: int = Field(1, ge=1, le=100)
    session_id: Optional[str] = None


class CartQuantityUpdate(BaseModel):
    quantity: int = Field(..., ge=1, le=100)
    session_id: Optional[str] = None


def _resolve_merchant(db: Session, merchant_id: Optional[str]):
    if merchant_id:
        merchant = db.query(Merchant).filter(Merchant.id == merchant_id).first()
    else:
        merchant = db.query(Merchant).first()

    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found.")

    return merchant


def _get_cart(db: Session, merchant_id: str, session_id: str):
    cart = (
        db.query(Cart)
        .filter(
            Cart.merchant_id == merchant_id,
            Cart.session_id == session_id,
        )
        .first()
    )

    if not cart:
        cart = Cart(
            merchant_id=merchant_id,
            session_id=session_id,
            currency="INR",
            total_amount=Decimal("0.00")
        )
        db.add(cart)
        db.commit()
        db.refresh(cart)

    return cart


def _serialize_cart(cart: Cart):
    items = []

    for item in cart.items:
        product = item.product

        items.append({
            "product_id": str(item.product_id),
            "name": product.name if product else "Unknown Product",
            "quantity": item.quantity,
            "unit_price": float(item.unit_price_snapshot),
            "subtotal": float(
                Decimal(str(item.quantity)) *
                Decimal(str(item.unit_price_snapshot))
            ),
            "image_url": (
                product.attributes.get("image_url")
                if product and isinstance(product.attributes, dict)
                else None
            ),
        })

    total = sum(Decimal(str(item["subtotal"])) for item in items)

    return {
        "id": str(cart.id),
        "session_id": cart.session_id,
        "merchant_id": str(cart.merchant_id),
        "items": items,
        "total_amount": float(total),
        "currency": cart.currency or "INR",
    }


@router.get("")
def get_cart(
    session_id: str,
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    merchant = _resolve_merchant(db, merchant_id)
    cart = _get_cart(db, str(merchant.id), session_id)

    return _serialize_cart(cart)


@router.post("/items")
@router.post("")
def add_cart_item(
    payload: CartItemAdd,
    session_id: Optional[str] = Query(None),
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    active_session_id = session_id or payload.session_id
    if not active_session_id:
        raise HTTPException(status_code=400, detail="session_id is required.")

    merchant = _resolve_merchant(db, merchant_id)
    cart = _get_cart(db, str(merchant.id), active_session_id)

    product = (
        db.query(Product)
        .filter(
            Product.id == payload.product_id,
            Product.merchant_id == merchant.id,
            Product.is_active == True,
        )
        .first()
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    inventory = (
        db.query(Inventory)
        .filter(Inventory.product_id == payload.product_id)
        .first()
    )
    available = inventory.stock_quantity if inventory else 0

    item = (
        db.query(CartItem)
        .filter(
            CartItem.cart_id == cart.id,
            CartItem.product_id == payload.product_id,
        )
        .first()
    )

    current_qty = item.quantity if item else 0
    target_qty = current_qty + payload.quantity

    if available < target_qty:
        raise HTTPException(
            status_code=409,
            detail=f"Insufficient inventory. Requested total: {target_qty}, Available: {available}.",
        )

    if item:
        item.quantity = target_qty
        item.unit_price_snapshot = Decimal(str(product.price))
    else:
        item = CartItem(
            cart_id=cart.id,
            product_id=product.id,
            quantity=payload.quantity,
            unit_price_snapshot=Decimal(str(product.price)),
        )
        db.add(item)

    db.commit()
    db.refresh(cart)

    serialized = _serialize_cart(cart)
    cart.total_amount = Decimal(str(serialized["total_amount"]))
    db.commit()

    return serialized


@router.patch("/items/{product_id}")
def update_cart_item(
    product_id: str,
    payload: CartQuantityUpdate,
    session_id: Optional[str] = Query(None),
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    active_session_id = session_id or payload.session_id
    if not active_session_id:
        raise HTTPException(status_code=400, detail="session_id is required.")

    merchant = _resolve_merchant(db, merchant_id)

    cart = (
        db.query(Cart)
        .filter(
            Cart.merchant_id == merchant.id,
            Cart.session_id == active_session_id,
        )
        .first()
    )

    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found.")

    item = (
        db.query(CartItem)
        .filter(
            CartItem.cart_id == cart.id,
            CartItem.product_id == product_id,
        )
        .first()
    )

    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found.")

    inventory = (
        db.query(Inventory)
        .filter(Inventory.product_id == product_id)
        .first()
    )

    if not inventory or inventory.stock_quantity < payload.quantity:
        available = inventory.stock_quantity if inventory else 0
        raise HTTPException(
            status_code=409,
            detail=f"Insufficient inventory. Available: {available}.",
        )

    # Re-read authoritative product price.
    product = (
        db.query(Product)
        .filter(
            Product.id == product_id,
            Product.merchant_id == merchant.id,
            Product.is_active == True,
        )
        .first()
    )

    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    item.quantity = payload.quantity
    item.unit_price_snapshot = Decimal(str(product.price))

    db.commit()
    db.refresh(cart)

    serialized = _serialize_cart(cart)
    cart.total_amount = Decimal(str(serialized["total_amount"]))
    db.commit()

    return serialized


@router.delete("/items/{product_id}")
def remove_cart_item(
    product_id: str,
    session_id: str = Query(...),
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    merchant = _resolve_merchant(db, merchant_id)

    cart = (
        db.query(Cart)
        .filter(
            Cart.merchant_id == merchant.id,
            Cart.session_id == session_id,
        )
        .first()
    )

    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found.")

    item = (
        db.query(CartItem)
        .filter(
            CartItem.cart_id == cart.id,
            CartItem.product_id == product_id,
        )
        .first()
    )

    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found.")

    db.delete(item)
    db.commit()

    db.refresh(cart)

    serialized = _serialize_cart(cart)
    cart.total_amount = Decimal(str(serialized["total_amount"]))
    db.commit()

    return serialized


@router.delete("")
def clear_cart(
    session_id: str = Query(...),
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    merchant = _resolve_merchant(db, merchant_id)

    cart = (
        db.query(Cart)
        .filter(
            Cart.merchant_id == merchant.id,
            Cart.session_id == session_id,
        )
        .first()
    )

    if not cart:
        return {
            "id": "",
            "session_id": session_id,
            "merchant_id": str(merchant.id),
            "items": [],
            "total_amount": 0.0,
            "currency": "INR",
        }

    for item in list(cart.items):
        db.delete(item)

    cart.total_amount = Decimal("0.00")
    db.commit()
    db.refresh(cart)

    return _serialize_cart(cart)
