"""
Controlled Buyer Agent Tools.
Explicitly defined, permission-governed tools for the AI Buyer Agent.
"""

from decimal import Decimal
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.tools.registry import tool_registry
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.merchant import Merchant
from app.database.models.cart import Cart, CartItem
from app.database.models.purchase_intent import PurchaseIntent
from app.database.models.base import generate_uuid
from app.services.agent_catalog_service import AgentCatalogService
from app.services.price_intelligence.canonical_service import CanonicalPriceIntelligenceService
from app.policies.policy_engine import PolicyEngine
from app.schemas.agent_catalog import AgentSearchRequest

@tool_registry.register(
    name="search_products",
    description="Searches catalog products with strict deterministic hard constraints (budget, brand, category, variants).",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search keyword or natural language query"},
            "category": {"type": "string", "description": "Product category filter (e.g. running shoes, apparel, water bottle)"},
            "budget_max": {"type": "number", "description": "Maximum price ceiling in INR"},
            "min_price": {"type": "number", "description": "Minimum price in INR"},
            "brand": {"type": "string", "description": "Brand name filter (e.g. Nike, Adidas, Puma)"},
            "color": {"type": "string", "description": "Color variant filter (e.g. Black, White, Navy Blue)"},
            "size": {"type": "string", "description": "Size variant filter (e.g. Medium, Large, UK 9)"},
            "in_stock_only": {"type": "boolean", "description": "Only return products currently in stock"}
        }
    },
    required_permission="READ_PRODUCTS",
    side_effect=False,
    authorization_requirement="PUBLIC"
)
def tool_search_products(db: Session, merchant_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    b_max = kwargs.get("budget_max") if kwargs.get("budget_max") is not None else kwargs.get("max_price")
    min_p = kwargs.get("min_price")
    req = AgentSearchRequest(
        query=kwargs.get("query"),
        category=kwargs.get("category"),
        budget_max=b_max,
        min_price=min_p,
        brand=kwargs.get("brand"),
        color=kwargs.get("color"),
        size=kwargs.get("size"),
        availability="in_stock" if kwargs.get("in_stock_only", True) else "all",
        merchant_id=merchant_id,
        limit=kwargs.get("limit", 20)
    )
    res = AgentCatalogService.search_catalog(db, req)
    results = []
    for p in res.results:
        d = p.model_dump()
        d["id"] = p.product_id
        d["product_id"] = p.product_id
        d["stock"] = p.stock_quantity
        d["stock_quantity"] = p.stock_quantity
        results.append(d)
    return {
        "count": len(results),
        "results": results,
        "applied_filters": res.applied_filters
    }

@tool_registry.register(
    name="get_product",
    description="Retrieves authoritative product details, variants, canonical style identity, and buyability for a specific product ID.",
    parameters={
        "type": "object",
        "properties": {
            "product_id": {"type": "string", "description": "The unique product ID"}
        },
        "required": ["product_id"]
    },
    required_permission="READ_PRODUCTS",
    side_effect=False,
    authorization_requirement="PUBLIC"
)
def tool_get_product(db: Session, product_id: str, **kwargs) -> Dict[str, Any]:
    try:
        p = AgentCatalogService.get_product_by_id(db, product_id)
        return {"success": True, "product": p.model_dump()}
    except Exception as e:
        return {"success": False, "error": str(e)}

@tool_registry.register(
    name="check_inventory",
    description="Authoritatively checks real-time inventory and availability for a product and optional variant.",
    parameters={
        "type": "object",
        "properties": {
            "product_id": {"type": "string", "description": "The unique product ID"},
            "variant_id": {"type": "string", "description": "Optional variant identifier (e.g. Classic Black)"},
            "requested_quantity": {"type": "integer", "description": "Quantity to verify", "default": 1}
        },
        "required": ["product_id"]
    },
    required_permission="READ_INVENTORY",
    side_effect=False,
    authorization_requirement="PUBLIC"
)
def tool_check_inventory(db: Session, product_id: str, variant_id: Optional[str] = None, requested_quantity: int = 1, **kwargs) -> Dict[str, Any]:
    avail = AgentCatalogService.get_product_availability(db, product_id)
    is_sufficient = avail.in_stock and (avail.stock_quantity >= requested_quantity)
    return {
        "product_id": product_id,
        "variant_id": variant_id,
        "available": is_sufficient,
        "stock_quantity": avail.stock_quantity,
        "requested_quantity": requested_quantity,
        "agent_buyable": avail.agent_buyable and is_sufficient,
        "reason": None if is_sufficient else "INSUFFICIENT_STOCK"
    }

@tool_registry.register(
    name="compare_prices",
    description="Performs canonical Buyhatke-style multi-store price intelligence comparison for a product across verified retailers.",
    parameters={
        "type": "object",
        "properties": {
            "product_id": {"type": "string", "description": "The unique product ID"},
            "variant_id": {"type": "string", "description": "Optional variant identifier"}
        },
        "required": ["product_id"]
    },
    required_permission="READ_PRODUCTS",
    side_effect=False,
    authorization_requirement="PUBLIC"
)
def tool_compare_prices(db: Session, product_id: str, variant_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    try:
        comp = CanonicalPriceIntelligenceService.get_canonical_comparison(db, product_id, variant_id=variant_id)
        return {
            "success": True,
            "product_name": comp.get("product_name"),
            "apex_price": comp.get("apex_price"),
            "lowest_verified_price": comp.get("lowest_verified_price"),
            "lowest_store": comp.get("lowest_store"),
            "apex_is_lowest": comp.get("apex_is_lowest"),
            "checked_sources": comp.get("checked_sources"),
            "summary_text": comp.get("summary_text"),
            "offers_count": len(comp.get("offers", []))
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@tool_registry.register(
    name="create_purchase_intent",
    description="Creates an immutable server-authoritative PurchaseIntent and evaluates governance policy limits.",
    parameters={
        "type": "object",
        "properties": {
            "product_id": {"type": "string", "description": "Product ID to purchase"},
            "variant_id": {"type": "string", "description": "Variant ID (e.g. Classic Black-M)"},
            "quantity": {"type": "integer", "description": "Quantity to order (1 to 5)", "default": 1},
            "delivery_address": {"type": "object", "description": "Customer delivery address"},
            "coupon_code": {"type": "string", "description": "Optional promotional coupon"},
            "use_coins": {"type": "boolean", "description": "Whether to redeem loyalty coins"}
        },
        "required": ["product_id"]
    },
    required_permission="CREATE_PURCHASE_INTENT",
    side_effect=True,
    authorization_requirement="AUTHENTICATED_CUSTOMER"
)
def tool_create_purchase_intent(
    db: Session,
    product_id: str,
    buyer_id: str,
    merchant_id: Optional[str] = None,
    session_id: Optional[str] = None,
    variant_id: Optional[str] = None,
    quantity: int = 1,
    delivery_address: Optional[Dict[str, Any]] = None,
    coupon_code: Optional[str] = None,
    use_coins: bool = False,
    trace_id: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    # 1. Product & Inventory Validation
    product = db.query(Product).filter(Product.id == product_id, Product.is_active == True).first()
    if not product:
        return {"success": False, "error": f"Product '{product_id}' not found or inactive."}

    inv = db.query(Inventory).filter(Inventory.product_id == product.id).first()
    if not inv or inv.stock_quantity < quantity:
        return {"success": False, "error": "Insufficient inventory."}

    # 2. Server-Authoritative Price Calculation
    unit_price = Decimal(str(product.price))
    raw_subtotal = unit_price * Decimal(str(quantity))
    discount_amount = Decimal("0.00")

    if coupon_code and coupon_code.upper() in ["SAVE500", "WELCOME10"]:
        if coupon_code.upper() == "SAVE500" and raw_subtotal >= Decimal("2000"):
            discount_amount += Decimal("500.00")
        elif coupon_code.upper() == "WELCOME10":
            discount_amount += round(raw_subtotal * Decimal("0.10"), 2)

    total_amount = max(Decimal("1.00"), raw_subtotal - discount_amount)
    m_id = product.merchant_id or merchant_id

    # 3. Create Server-Authoritative Cart
    cart_sess = session_id or f"sess_buyer_{generate_uuid()[:12]}"
    cart = Cart(
        id=f"cart_bi_{generate_uuid()[:12]}",
        merchant_id=m_id,
        session_id=cart_sess,
        status="active",
        currency="INR",
        total_amount=total_amount
    )
    db.add(cart)
    db.flush()

    cart_item = CartItem(
        id=f"ci_bi_{generate_uuid()[:12]}",
        cart_id=cart.id,
        product_id=product.id,
        quantity=quantity,
        unit_price_snapshot=unit_price
    )
    db.add(cart_item)
    db.flush()

    # 4. Create Immutable PurchaseIntent
    intent_id = f"pi_bi_{generate_uuid()[:12]}"
    t_id = trace_id or f"trc_bi_{generate_uuid()[:12]}"
    summary = {
        "items": [{
            "product_id": str(product.id),
            "name": product.name,
            "variant_id": variant_id,
            "quantity": quantity,
            "unit_price": float(unit_price),
            "subtotal": float(raw_subtotal)
        }],
        "raw_subtotal": float(raw_subtotal),
        "discount_amount": float(discount_amount),
        "total_amount": float(total_amount),
        "coupon_code": coupon_code,
        "use_coins": use_coins
    }

    intent = PurchaseIntent(
        id=intent_id,
        merchant_id=m_id,
        buyer_id=buyer_id,
        session_id=cart_sess,
        cart_id=cart.id,
        trace_id=t_id,
        product_summary=summary,
        requested_amount=total_amount,
        currency="INR",
        status="CREATED",
        delivery_address=delivery_address or {}
    )
    db.add(intent)
    db.commit()
    db.refresh(intent)

    # 5. Deterministic Policy Evaluation
    policy_eval = PolicyEngine.evaluate_purchase_intent(
        db=db,
        purchase_intent_id=intent.id,
        merchant_id=m_id,
        agent_id=None
    )

    return {
        "success": True,
        "purchase_intent_id": intent.id,
        "trace_id": t_id,
        "status": intent.status,
        "product_id": str(product.id),
        "product_name": product.name,
        "variant_id": variant_id,
        "quantity": quantity,
        "unit_price": float(unit_price),
        "discount_amount": float(discount_amount),
        "total_amount": float(total_amount),
        "governance_decision": policy_eval.get("decision", "ALLOW"),
        "requires_human_approval": policy_eval.get("requires_human_approval", False),
        "order_review": {
            "product_name": product.name,
            "variant_id": variant_id or "Standard",
            "quantity": quantity,
            "unit_price": float(unit_price),
            "discount_amount": float(discount_amount),
            "total_amount": float(total_amount),
            "governance": policy_eval.get("decision", "ALLOW"),
            "payment_provider": "RAZORPAY_TEST_MODE"
        }
    }

@tool_registry.register(
    name="get_purchase_intent",
    description="Retrieves a PurchaseIntent and its current governance and payment verification status.",
    parameters={
        "type": "object",
        "properties": {
            "purchase_intent_id": {"type": "string", "description": "PurchaseIntent ID"}
        },
        "required": ["purchase_intent_id"]
    },
    required_permission="READ_PURCHASE_INTENT",
    side_effect=False,
    authorization_requirement="AUTHENTICATED_CUSTOMER"
)
def tool_get_purchase_intent(db: Session, purchase_intent_id: str, buyer_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    q = db.query(PurchaseIntent).filter(PurchaseIntent.id == purchase_intent_id)
    if buyer_id:
        q = q.filter(PurchaseIntent.buyer_id == buyer_id)
    intent = q.first()
    if not intent:
        return {"success": False, "error": "Purchase intent not found or unauthorized."}

    return {
        "success": True,
        "purchase_intent_id": intent.id,
        "status": intent.status,
        "total_amount": float(intent.requested_amount),
        "currency": intent.currency,
        "summary": intent.product_summary,
        "delivery_address": intent.delivery_address
    }

@tool_registry.register(
    name="get_checkout_state",
    description="Retrieves the order review, governance evaluation, and Razorpay payment checkout readiness for a purchase intent.",
    parameters={
        "type": "object",
        "properties": {
            "purchase_intent_id": {"type": "string", "description": "PurchaseIntent ID"}
        },
        "required": ["purchase_intent_id"]
    },
    required_permission="READ_CART",
    side_effect=False,
    authorization_requirement="AUTHENTICATED_CUSTOMER"
)
def tool_get_checkout_state(db: Session, purchase_intent_id: str, buyer_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    q = db.query(PurchaseIntent).filter(PurchaseIntent.id == purchase_intent_id)
    if buyer_id:
        q = q.filter(PurchaseIntent.buyer_id == buyer_id)
    intent = q.first()
    if not intent:
        return {"success": False, "error": "Purchase intent not found."}

    summary = intent.product_summary or {}
    return {
        "success": True,
        "purchase_intent_id": intent.id,
        "order_review": {
            "items": summary.get("items", []),
            "subtotal": summary.get("raw_subtotal", float(intent.requested_amount)),
            "discount": summary.get("discount_amount", 0.0),
            "final_amount": float(intent.requested_amount),
            "currency": intent.currency or "INR",
            "governance_status": intent.status,
            "payment_ready": intent.status in ["CREATED", "APPROVED", "AUTHORIZED"]
        }
    }
