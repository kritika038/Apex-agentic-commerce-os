from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.database.models.agent import Agent
from app.database.models.merchant import Merchant
from app.database.models.user import User
from app.schemas.policy import AgentResponse, AgentFirewallResponse, AgentFirewallRule
from app.auth.deps import get_current_user, get_optional_current_user

router = APIRouter(tags=["Agents & Permissions"])

ALL_PERMISSIONS = [
    "READ_PRODUCTS", "READ_INVENTORY", "CREATE_CART", "READ_CART", "MODIFY_CART",
    "CALCULATE_CART", "RECOMMEND_PRODUCT", "CREATE_RECOMMENDATION",
    "CREATE_PAYMENT_ORDER", "READ_PAYMENT_STATUS", "RECONCILE_PAYMENT",
    "MANAGE_POLICY", "AUTHORIZE_TRANSACTION"
]

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

@router.get("", response_model=List[AgentResponse])
def list_agents(
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    m_id = _resolve_merchant_id(current_user, db, merchant_id)
    agents = db.query(Agent).filter(Agent.merchant_id == m_id).all()
    
    results = []
    for ag in agents:
        results.append(AgentResponse(
            id=ag.id,
            merchant_id=ag.merchant_id,
            name=ag.name,
            type=ag.type,
            version=ag.version,
            model=ag.model,
            status=ag.status,
            permissions=ag.permission_names
        ))
    return results

@router.get("/firewall", response_model=AgentFirewallResponse)
def get_agent_firewall(
    merchant_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Exposes the active Agent Permission Firewall matrix.
    Visualizes least-privilege boundaries, forbidden permissions, and tool execution scopes.
    """
    m_id = _resolve_merchant_id(current_user, db, merchant_id)
    
    # 1. ShoppingAgent
    shopping_granted = ["READ_PRODUCTS", "READ_INVENTORY", "CREATE_CART", "READ_CART", "MODIFY_CART", "CALCULATE_CART", "RECOMMEND_PRODUCT"]
    shopping_forbidden = [p for p in ALL_PERMISSIONS if p not in shopping_granted]
    
    # 2. SalesAgent
    sales_granted = ["READ_PRODUCTS", "READ_INVENTORY", "READ_CART", "CREATE_RECOMMENDATION"]
    sales_forbidden = [p for p in ALL_PERMISSIONS if p not in sales_granted]

    # 3. PaymentAgent (Backend Service)
    payment_granted = ["CREATE_PAYMENT_ORDER", "READ_PAYMENT_STATUS", "RECONCILE_PAYMENT"]
    payment_forbidden = [p for p in ALL_PERMISSIONS if p not in payment_granted]

    # 4. External AI Buyer (Protocol)
    buyer_granted = ["READ_PRODUCTS", "READ_INVENTORY", "CREATE_CART", "MODIFY_CART", "CREATE_PURCHASE_INTENT", "READ_AUTHORIZATION_STATUS"]
    buyer_forbidden = ["AUTHORIZE_TRANSACTION", "MANAGE_POLICY", "CREATE_PAYMENT_ORDER", "RECONCILE_PAYMENT", "MODIFY_PRICE", "OVERRIDE_CURRENCY"]

    rules = [
        AgentFirewallRule(
            agent_id="shopping_agent_v1",
            name="Shopping Assistant Agent",
            type="SHOPPING_AGENT",
            version="1.0.0",
            status="ACTIVE",
            granted_permissions=shopping_granted,
            forbidden_permissions=shopping_forbidden,
            allowed_tools=["search_products", "add_to_cart", "view_cart", "calculate_cart_total"],
            isolation_level="SANDBOXED_CATALOG_CART",
            can_authorize_payments=False,
            can_modify_prices=False,
            can_override_policies=False
        ),
        AgentFirewallRule(
            agent_id="sales_agent_v1",
            name="Sales Optimization Agent",
            type="SALES_AGENT",
            version="1.0.0",
            status="ACTIVE",
            granted_permissions=sales_granted,
            forbidden_permissions=sales_forbidden,
            allowed_tools=["search_products", "get_product_stock", "view_cart", "generate_cross_sell"],
            isolation_level="READ_ONLY_RECOMMENDATIONS",
            can_authorize_payments=False,
            can_modify_prices=False,
            can_override_policies=False
        ),
        AgentFirewallRule(
            agent_id="payment_agent_v1",
            name="Payment Settlement Gateway",
            type="PAYMENT_AGENT",
            version="1.0.0",
            status="ACTIVE",
            granted_permissions=payment_granted,
            forbidden_permissions=payment_forbidden,
            allowed_tools=["create_provider_order", "fetch_payment_status", "reconcile_transaction"],
            isolation_level="GATED_AUTHORIZATION_BOUNDARY",
            can_authorize_payments=False, # Only PolicyEngine / Human can authorize
            can_modify_prices=False,
            can_override_policies=False
        ),
        AgentFirewallRule(
            agent_id="external_ai_buyer_v1",
            name="Autonomous AI Buyer Protocol",
            type="EXTERNAL_BUYER",
            version="1.0.0",
            status="ACTIVE",
            granted_permissions=buyer_granted,
            forbidden_permissions=buyer_forbidden,
            allowed_tools=["protocol_discover", "protocol_recommend", "protocol_purchase_intent", "protocol_authorization_lookup", "protocol_payment_request"],
            isolation_level="MACHINE_TO_MACHINE_SANDBOX",
            can_authorize_payments=False,
            can_modify_prices=False,
            can_override_policies=False
        )
    ]

    return AgentFirewallResponse(
        merchant_id=m_id,
        firewall_status="ACTIVE",
        total_agents=len(rules),
        agents=rules
    )
