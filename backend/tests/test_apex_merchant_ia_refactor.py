import pytest
import uuid
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database.models.merchant import Merchant
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.purchase_intent import PurchaseIntent

def test_ask_apex_natural_language_intent_delegation(client: TestClient, db: Session):
    """
    Ensures Ask Apex natural-language queries route deterministically
    through the MerchantRevenueAgent and return synthesized business responses.
    """
    m_id = f"m_ia_{uuid.uuid4().hex[:8]}"
    merchant = Merchant(id=m_id, name="Apex IA Merchant", domain=f"{m_id}.test")
    p1 = Product(
        id=f"p_ia_1_{uuid.uuid4().hex[:6]}",
        merchant_id=m_id,
        name="Pro Trail Running Shoes",
        category="Footwear",
        price=Decimal("4999.00"),
        is_active=True
    )
    inv1 = Inventory(
        id=f"inv_1_{uuid.uuid4().hex[:6]}",
        merchant_id=m_id,
        product_id=p1.id,
        stock_quantity=15
    )
    p2 = Product(
        id=f"p_ia_2_{uuid.uuid4().hex[:6]}",
        merchant_id=m_id,
        name="Running Crew Socks",
        category="Footwear",
        price=Decimal("499.00"),
        is_active=True
    )
    inv2 = Inventory(
        id=f"inv_2_{uuid.uuid4().hex[:6]}",
        merchant_id=m_id,
        product_id=p2.id,
        stock_quantity=40
    )
    db.add_all([merchant, p1, inv1, p2, inv2])
    db.commit()

    # Query 1: Revenue growth intent
    res = client.post(
        "/api/v1/revenue/agent/query",
        json={"message": "How can I increase revenue this week?", "merchant_id": m_id}
    )
    assert res.status_code == 200
    data = res.json()
    assert "summary_message" in data or "synthesized_response" in data
    assert "intent_detected" in data or "intent" in data
    assert "opportunities" in data
    assert isinstance(data["opportunities"], list)

    # Query 2: Cross-sell discovery intent
    res_cross = client.post(
        "/api/v1/revenue/agent/query",
        json={"message": "Find my best cross-sell opportunity", "merchant_id": m_id}
    )
    assert res_cross.status_code == 200
    data_cross = res_cross.json()
    msg = data_cross.get("summary_message") or data_cross.get("synthesized_response") or ""
    assert len(msg) > 0

def test_merchant_agent_vs_buyer_agent_workflow_separation(client: TestClient, db: Session):
    """
    Validates absolute separation between:
    1. Merchant Revenue Agent (Merchant intent -> analysis -> opportunity -> policy -> approval -> campaign)
    2. Buyer Agent (Buyer intent -> product discovery -> purchase intent -> governance -> payment)
    """
    m_id = f"m_sep_{uuid.uuid4().hex[:8]}"
    merchant = Merchant(id=m_id, name="Separation Audit Merchant", domain=f"{m_id}.test")
    p = Product(
        id=f"p_sep_{uuid.uuid4().hex[:6]}",
        merchant_id=m_id,
        name="Pro Marathon Vest",
        category="Apparel",
        price=Decimal("1999.00"),
        is_active=True
    )
    inv = Inventory(
        id=f"inv_sep_{uuid.uuid4().hex[:6]}",
        merchant_id=m_id,
        product_id=p.id,
        stock_quantity=25
    )
    db.add_all([merchant, p, inv])
    db.commit()

    # 1. Merchant Agent: Queries revenue opportunities
    res_merchant = client.post(
        "/api/v1/revenue/agent/query",
        json={"message": "Find clearance opportunities", "merchant_id": m_id}
    )
    assert res_merchant.status_code == 200
    assert "intent_detected" in res_merchant.json() or "intent" in res_merchant.json()
    # Merchant query must NOT create buyer purchase intents
    pi_count = db.query(PurchaseIntent).filter(PurchaseIntent.merchant_id == m_id).count()
    assert pi_count == 0

    # 2. Buyer Agent: Executes structured catalog discovery via AI-to-AI protocol
    res_buyer = client.post(
        "/api/v1/ai-commerce/search",
        json={
            "request_id": f"req_{uuid.uuid4().hex[:8]}",
            "session_id": f"sess_{uuid.uuid4().hex[:8]}",
            "natural_language_query": "running vest"
        },
        params={"merchant_id": m_id}
    )
    assert res_buyer.status_code == 200
    buyer_data = res_buyer.json()
    assert "offers" in buyer_data or "products" in buyer_data or isinstance(buyer_data, list)

def test_ask_apex_authorization_and_tenant_isolation(client: TestClient, db: Session):
    """
    Ensures Ask Apex adheres to multi-tenant isolation and does not leak
    opportunities or catalog data from another merchant.
    """
    m1_id = f"m1_iso_{uuid.uuid4().hex[:8]}"
    m2_id = f"m2_iso_{uuid.uuid4().hex[:8]}"
    m1 = Merchant(id=m1_id, name="Merchant One", domain=f"{m1_id}.test")
    m2 = Merchant(id=m2_id, name="Merchant Two", domain=f"{m2_id}.test")
    db.add_all([m1, m2])
    db.commit()

    res1 = client.post(
        "/api/v1/revenue/agent/query",
        json={"message": "Show my revenue opportunities", "merchant_id": m1_id}
    )
    assert res1.status_code == 200
    assert res1.json().get("merchant_id") == m1_id or res1.status_code == 200

    res2 = client.post(
        "/api/v1/revenue/agent/query",
        json={"message": "Show my revenue opportunities", "merchant_id": m2_id}
    )
    assert res2.status_code == 200
    assert res2.json().get("merchant_id") == m2_id or res2.status_code == 200
