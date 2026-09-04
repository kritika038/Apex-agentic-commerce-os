import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

def test_protocol_capabilities_discovery(client: TestClient, db: Session, setup_test_data):
    """
    Test: External AI agents can discover machine-readable merchant capabilities and operations.
    """
    m1_id = setup_test_data["m1"]

    res = client.get(f"/api/v1/protocol/capabilities?merchant_id={m1_id}")
    assert res.status_code == 200
    data = res.json()

    assert data["protocol_version"] == "1.0.0"
    assert data["merchant_id"] == m1_id
    assert data["supported_currency"] == "INR"
    assert "discover" in data["operations"]
    assert "recommend" in data["operations"]
    assert "purchase_intent" in data["operations"]
    assert "authorization_lookup" in data["operations"]
    assert "payment_request" in data["operations"]

    # Security guarantees
    assert data["security_guarantees"]["price_authority"] == "DATABASE_GROUNDED"
    assert data["security_guarantees"]["inventory_authority"] == "DATABASE_GROUNDED"
    assert data["security_guarantees"]["payment_authority"] == "RESTRICTED_AUTHORIZATION_BOUNDARY"
    assert data["security_guarantees"]["audit_integrity"] == "SHA256_HASH_CHAINED"

def test_agent_firewall_matrix_exposure(client: TestClient, db: Session, setup_test_data):
    """
    Test: Agent Permission Firewall matrix accurately reflects least-privilege boundaries
    and confirms no agent can authorize payments or modify prices.
    """
    m1_id = setup_test_data["m1"]

    res = client.get(f"/api/v1/agents/firewall?merchant_id={m1_id}")
    assert res.status_code == 200
    data = res.json()

    assert data["firewall_status"] == "ACTIVE"
    assert data["total_agents"] >= 4

    agents = {a["agent_id"]: a for a in data["agents"]}
    
    # Shopping Agent checks
    assert "shopping_agent_v1" in agents
    shop = agents["shopping_agent_v1"]
    assert "READ_PRODUCTS" in shop["granted_permissions"]
    assert "CREATE_PAYMENT_ORDER" in shop["forbidden_permissions"]
    assert shop["can_authorize_payments"] is False
    assert shop["can_modify_prices"] is False

    # Sales Agent checks
    assert "sales_agent_v1" in agents
    sales = agents["sales_agent_v1"]
    assert "CREATE_RECOMMENDATION" in sales["granted_permissions"]
    assert "CREATE_CART" in sales["forbidden_permissions"]
    assert "CREATE_PAYMENT_ORDER" in sales["forbidden_permissions"]
    assert sales["can_authorize_payments"] is False

    # Payment Agent boundary
    assert "payment_agent_v1" in agents
    pay = agents["payment_agent_v1"]
    assert "CREATE_PAYMENT_ORDER" in pay["granted_permissions"]
    assert pay["can_authorize_payments"] is False # Only PolicyEngine / Human can authorize
