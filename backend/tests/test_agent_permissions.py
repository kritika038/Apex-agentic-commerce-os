import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database.models.agent import Agent, Permission, AgentPermission
from app.tools.registry import tool_registry

def test_agent_normalized_permissions_structure(db: Session, setup_test_data):
    m1_id = setup_test_data["m1"]

    # 1. Create permissions
    p_read = Permission(name="READ_PRODUCTS", description="Read products", category="catalog")
    p_cart = Permission(name="MODIFY_CART", description="Modify cart", category="cart")
    p_pay = Permission(name="CREATE_PAYMENT_ORDER", description="Payment", category="payment")
    db.add_all([p_read, p_cart, p_pay])
    db.flush()

    # 2. Create Agent
    sales_agent = Agent(merchant_id=m1_id, name="SalesAgent", type="sales", status="active")
    db.add(sales_agent)
    db.flush()

    assoc = AgentPermission(agent_id=sales_agent.id, permission_id=p_read.id)
    db.add(assoc)
    db.commit()

    # Verify relationships
    ag_db = db.query(Agent).filter(Agent.id == sales_agent.id).first()
    assert "READ_PRODUCTS" in ag_db.permission_names
    assert "CREATE_PAYMENT_ORDER" not in ag_db.permission_names

def test_sales_agent_permission_denial_on_payment_tools(db: Session, setup_test_data):
    """
    Least Privilege: SalesAgent attempting to call unauthorized tools receives structured PERMISSION_DENIED.
    """
    m1_id = setup_test_data["m1"]
    
    # Tool requires CREATE_PAYMENT_ORDER
    err = tool_registry.verify_permission(
        tool_name="add_to_cart", # requires MODIFY_CART
        agent_permissions=["READ_PRODUCTS", "READ_CART", "CREATE_RECOMMENDATION"],
        agent_name="SalesAgent"
    )
    assert err is not None
    assert err["error"] == "PERMISSION_DENIED"
    assert err["agent"] == "SalesAgent"
    assert err["required_permission"] == "MODIFY_CART"

def test_agent_cannot_modify_policy(client: TestClient, setup_test_data):
    """
    AI agents without merchant user auth cannot modify policies (returns 401 Unauthorized).
    """
    m1_id = setup_test_data["m1"]
    
    # Anonymous or Agent attempt without user bearer token
    res = client.post("/api/v1/policies", json={
        "name": "Malicious Policy Override",
        "max_transaction_amount": 999999.0,
        "approval_threshold": 999999.0
    })
    assert res.status_code == 401
