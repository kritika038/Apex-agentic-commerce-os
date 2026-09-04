"""
Agent Commerce & AI Buyer Agent API Router.
Provides public machine-readable catalog discovery and authenticated buyer agent transactions.
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status, Header
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.database.session import get_db
from app.database.models.user import User
from app.database.models.merchant import Merchant
from app.auth.deps import get_optional_current_user, get_current_active_user
from app.services.agent_catalog_service import AgentCatalogService
from app.agents.buyer_agent import BuyerAgent
from app.tools.registry import tool_registry
from app.tools.buyer_tools import tool_create_purchase_intent, tool_get_purchase_intent
from app.schemas.agent_catalog import (
    AgentProductDetail,
    AgentCatalogResponse,
    AgentSearchRequest,
    AgentSearchResponse,
    AgentAvailabilityResponse,
    AgentPurchaseIntentCreate,
    AgentPurchaseIntentDetail,
    AgentBuyerActRequest,
    AgentBuyerActResponse,
    AgentToolDefinition
)

router = APIRouter(prefix="/agent", tags=["Agent Commerce & Buyer Agent"])

# -------------------------------------------------------------
# 1. Machine-Readable Catalog Discovery (PUBLIC_READ)
# -------------------------------------------------------------

@router.get("/catalog", response_model=AgentCatalogResponse)
def get_agent_catalog(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    query: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    brand: Optional[str] = Query(None),
    budget_max: Optional[float] = Query(None),
    min_price: Optional[float] = Query(None),
    availability: Optional[str] = Query(None),
    merchant_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Public machine-readable catalog discovery endpoint for external and internal AI buyers.
    Returns structured products, variants, canonical identity, purchase constraints, and buyability.
    """
    return AgentCatalogService.get_catalog(
        db=db,
        skip=skip,
        limit=limit,
        query=query,
        category=category,
        brand=brand,
        budget_max=budget_max,
        min_price=min_price,
        availability=availability,
        merchant_id=merchant_id
    )

@router.get("/products/{product_id}", response_model=AgentProductDetail)
def get_agent_product(
    product_id: str,
    db: Session = Depends(get_db)
):
    """
    Retrieves full machine-readable product structure, variants, canonical identity, and buyability.
    """
    return AgentCatalogService.get_product_by_id(db, product_id)

@router.post("/search", response_model=AgentSearchResponse)
def search_agent_catalog(
    request: AgentSearchRequest,
    db: Session = Depends(get_db)
):
    """
    Executes structured machine-readable search with strict hard constraints (budget, brand, category, variants).
    """
    return AgentCatalogService.search_catalog(db, request)

@router.get("/products/{product_id}/availability", response_model=AgentAvailabilityResponse)
def get_agent_product_availability(
    product_id: str,
    db: Session = Depends(get_db)
):
    """
    Authoritatively checks inventory stock and agent buyability for product and all variants.
    """
    return AgentCatalogService.get_product_availability(db, product_id)

@router.get("/tools", response_model=List[AgentToolDefinition])
def list_agent_tools():
    """
    Exposes controlled buyer agent tool definitions, schemas, permissions, and side-effect flags.
    """
    all_defs = tool_registry.list_all_tools()
    buyer_tools = ["search_products", "get_product", "check_inventory", "compare_prices", "create_purchase_intent", "get_purchase_intent", "get_checkout_state"]
    return [
        AgentToolDefinition(
            name=d.name,
            description=d.description,
            side_effect=d.side_effect,
            authorization_requirement=d.authorization_requirement,
            parameters=d.parameters,
            output_schema=d.output_schema
        )
        for d in all_defs if d.name in buyer_tools
    ]

# -------------------------------------------------------------
# 2. Conversational Buyer Agent (Interactive & Multi-Turn)
# -------------------------------------------------------------

@router.post("/buyer/act", response_model=AgentBuyerActResponse)
def buyer_agent_act(
    request: AgentBuyerActRequest,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """
    Executes a multi-turn conversational AI Buyer Agent turn.
    Performs intent analysis, controlled tool execution, factual explanation, and governed checkout preparation.
    """
    agent = BuyerAgent(db=db, user=current_user, session_id=request.session_id)
    return agent.act(
        message=request.message,
        delivery_address=request.delivery_address,
        coupon_code=request.coupon_code,
        use_coins=request.use_coins
    )

@router.post("/chat", response_model=AgentBuyerActResponse)
def buyer_agent_chat_alias(
    request: AgentBuyerActRequest,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """
    Alias endpoint for buyer agent chat.
    """
    return buyer_agent_act(request, current_user, db)

# -------------------------------------------------------------
# 3. Governed Purchase Intent API (AUTHENTICATED_CUSTOMER / AUTHORIZED_AGENT)
# -------------------------------------------------------------

@router.post("/purchase-intent", response_model=AgentPurchaseIntentDetail)
def create_agent_purchase_intent(
    payload: AgentPurchaseIntentCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Creates an immutable server-authoritative PurchaseIntent and evaluates governance policy.
    Requires customer authentication. Server derives buyer identity from authenticated token.
    """
    res = tool_create_purchase_intent(
        db=db,
        product_id=payload.product_id,
        buyer_id=current_user.id,
        variant_id=payload.variant_id,
        quantity=payload.quantity,
        delivery_address=payload.delivery_address,
        coupon_code=payload.coupon_code,
        use_coins=payload.use_coins
    )

    if not res.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=res.get("error", "Failed to create purchase intent.")
        )

    return AgentPurchaseIntentDetail(
        purchase_intent_id=res["purchase_intent_id"],
        status=res["status"],
        buyer_id=current_user.id,
        merchant_id=res.get("merchant_id", ""),
        product_id=res["product_id"],
        product_name=res["product_name"],
        variant_id=res.get("variant_id"),
        quantity=res["quantity"],
        authoritative_unit_price=res["unit_price"],
        total_amount=res["total_amount"],
        discount_amount=res.get("discount_amount", 0.0),
        currency="INR",
        governance_decision=res["governance_decision"],
        requires_human_approval=res["requires_human_approval"],
        trace_id=res["trace_id"],
        created_at=datetime.now(timezone.utc).isoformat(),
        order_review=res["order_review"],
        message="Purchase intent created and evaluated. Explicit customer payment confirmation required."
    )

@router.get("/purchase-intent/{purchase_intent_id}", response_model=Dict[str, Any])
def get_agent_purchase_intent(
    purchase_intent_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves purchase intent details and governance status. Enforces customer tenant isolation.
    """
    res = tool_get_purchase_intent(db, purchase_intent_id, buyer_id=current_user.id)
    if not res.get("success"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase intent not found or unauthorized."
        )
    return res
