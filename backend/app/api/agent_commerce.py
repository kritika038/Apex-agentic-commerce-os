from decimal import Decimal
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.merchant import Merchant
from app.database.models.purchase_intent import PurchaseIntent
from app.database.models.cart import Cart, CartItem
from app.database.models.base import generate_uuid
from app.policies.policy_engine import PolicyEngine

router = APIRouter(prefix="/agent-commerce", tags=["AI-to-AI Commerce"])

class AgentProductItem(BaseModel):
    product_id: str
    name: str
    description: Optional[str]
    category: str
    price: float
    currency: str = "INR"
    availability: str
    stock_quantity: int
    purchase_constraints: Dict[str, Any]

class AgentCatalogResponse(BaseModel):
    merchant_id: str
    merchant_name: str
    currency: str = "INR"
    total_products: int
    products: List[AgentProductItem]

class AgentPurchaseIntentCreate(BaseModel):
    agent_id: str
    customer_id: str
    product_id: str
    quantity: int = Field(1, ge=1)
    max_budget: float
    requires_human_approval: bool = True
    delivery_address: Optional[Dict[str, Any]] = None

class AgentPurchaseIntentResponse(BaseModel):
    purchase_intent_id: str
    status: str
    agent_id: str
    customer_id: str
    product_id: str
    product_name: str
    authoritative_unit_price: float
    total_amount: float
    currency: str
    policy_evaluation_status: str
    requires_human_approval: bool
    message: str

@router.get("/catalog", response_model=AgentCatalogResponse)
def get_agent_commerce_catalog(
    merchant_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Machine-readable discovery endpoint for external autonomous AI agents.
    Returns authoritative catalog facts directly from SQL database.
    """
    merchant = None
    if merchant_id:
        merchant = db.query(Merchant).filter(Merchant.id == merchant_id).first()
    if not merchant:
        merchant = db.query(Merchant).filter(Merchant.is_active == True).first()
    if not merchant:
        raise HTTPException(status_code=404, detail="No active merchant found.")

    products = db.query(Product).filter(
        Product.merchant_id == merchant.id,
        Product.is_active == True
    ).order_by(Product.price.asc()).all()

    items = []
    for p in products:
        stock = p.inventory.stock_quantity if p.inventory else 0
        items.append(AgentProductItem(
            product_id=p.id,
            name=p.name,
            description=p.description,
            category=p.category,
            price=float(p.price),
            currency=p.currency or "INR",
            availability="in_stock" if stock > 0 else "out_of_stock",
            stock_quantity=stock,
            purchase_constraints={
                "max_order_quantity": 5,
                "requires_approval_above": 5000.0,
                "allowed_currency": "INR"
            }
        ))

    return AgentCatalogResponse(
        merchant_id=merchant.id,
        merchant_name=merchant.name,
        currency="INR",
        total_products=len(items),
        products=items
    )

@router.post("/purchase-intent", response_model=AgentPurchaseIntentResponse)
def create_agent_purchase_intent(
    payload: AgentPurchaseIntentCreate,
    merchant_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Autonomous AI agent requests commerce intent.
    Deterministic backend validates product, authoritative pricing, stock, customer permission, and budget.
    """
    merchant = None
    if merchant_id:
        merchant = db.query(Merchant).filter(Merchant.id == merchant_id).first()
    if not merchant:
        merchant = db.query(Merchant).filter(Merchant.is_active == True).first()
    if not merchant:
        raise HTTPException(status_code=404, detail="No active merchant found.")

    # 1. Product & Inventory Validation
    product = db.query(Product).filter(
        Product.id == payload.product_id,
        Product.merchant_id == merchant.id,
        Product.is_active == True
    ).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product '{payload.product_id}' not found or inactive."
        )

    inv = db.query(Inventory).filter(
        Inventory.product_id == product.id,
        Inventory.merchant_id == merchant.id
    ).first()
    if not inv or inv.stock_quantity < payload.quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient inventory. Requested: {payload.quantity}, Available: {inv.stock_quantity if inv else 0}."
        )

    # 2. Authoritative Price & Budget Check
    unit_price = Decimal(str(product.price))
    total_amount = unit_price * Decimal(str(payload.quantity))
    max_budget = Decimal(str(payload.max_budget))

    if total_amount > max_budget:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Requested total (₹{total_amount:,.2f}) exceeds agent authorized budget (₹{max_budget:,.2f})."
        )
    # 3. Create Server-Authoritative Cart and CartItem
    agent_sess = f"sess_agent_{payload.agent_id[:16]}"
    cart = Cart(
        id=f"cart_agent_{generate_uuid()[:12]}",
        merchant_id=merchant.id,
        session_id=agent_sess,
        status="active",
        currency="INR",
        total_amount=total_amount
    )
    db.add(cart)
    db.flush()

    cart_item = CartItem(
        id=f"ci_agent_{generate_uuid()[:12]}",
        cart_id=cart.id,
        product_id=product.id,
        quantity=payload.quantity,
        unit_price_snapshot=unit_price
    )
    db.add(cart_item)
    db.flush()

    # 4. Create Immutable PurchaseIntent
    intent_id = f"pi_agent_{generate_uuid()[:12]}"
    summary = {
        "items": [{
            "product_id": product.id,
            "name": product.name,
            "quantity": payload.quantity,
            "price": float(unit_price),
            "subtotal": float(total_amount)
        }],
        "total_amount": float(total_amount),
        "agent_requested": True,
        "agent_id": payload.agent_id
    }

    intent = PurchaseIntent(
        id=intent_id,
        merchant_id=merchant.id,
        buyer_id=payload.customer_id,
        session_id=agent_sess,
        cart_id=cart.id,
        trace_id=f"trc_agent_{generate_uuid()[:12]}",
        product_summary=summary,
        requested_amount=total_amount,
        currency="INR",
        status="CREATED",
        delivery_address=payload.delivery_address or {}
    )
    db.add(intent)
    db.commit()
    db.refresh(intent)

    # 4. Deterministic Policy Evaluation
    eval_res = PolicyEngine.evaluate_purchase_intent(
        db=db,
        purchase_intent_id=intent.id,
        merchant_id=merchant.id,
        agent_id=payload.agent_id
    )

    return AgentPurchaseIntentResponse(
        purchase_intent_id=intent.id,
        status=intent.status,
        agent_id=payload.agent_id,
        customer_id=payload.customer_id,
        product_id=product.id,
        product_name=product.name,
        authoritative_unit_price=float(unit_price),
        total_amount=float(total_amount),
        currency="INR",
        policy_evaluation_status=eval_res.get("decision", "ALLOW"),
        requires_human_approval=eval_res.get("requires_human_approval", False),
        message=f"Purchase intent generated and evaluated against policy: {eval_res.get('decision', 'ALLOW')}."
    )
