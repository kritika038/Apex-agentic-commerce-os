import pytest
from decimal import Decimal
from fastapi.testclient import TestClient

from app.main import app
from app.database.session import get_db, SessionLocal
from app.database.models.merchant import Merchant
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.revenue_opportunity import RevenueOpportunity
from app.agents.merchant_growth_agent import MerchantGrowthAgent
from app.revenue.opportunity_engine import RevenueOpportunityEngine

client = TestClient(app)

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_1_merchant_growth_overview_real_signals(db_session):
    """
    Validates that MerchantGrowthAgent calculates metrics from real database models.
    """
    merchant = db_session.query(Merchant).filter(Merchant.is_active == True).first()
    assert merchant is not None

    overview = MerchantGrowthAgent.get_growth_overview(db_session, merchant.id)
    assert "total_gmv" in overview
    assert "total_orders" in overview
    assert "average_order_value" in overview
    assert "catalog_size" in overview
    assert overview["catalog_size"] > 0
    assert overview["currency"] == "INR"

def test_2_opportunity_generation_and_co_purchase_bundles(db_session):
    """
    Validates that RevenueOpportunityEngine discovers bundles, cross-sells,
    and inventory risks grounded in real catalog & inventory data.
    """
    merchant = db_session.query(Merchant).filter(Merchant.is_active == True).first()
    opps = RevenueOpportunityEngine.discover_opportunities(db_session, merchant.id)
    assert len(opps) >= 1

    types = {o.type for o in opps}
    assert "CROSS_SELL" in types or "BUNDLE" in types or "UPSELL" in types

    for o in opps:
        assert o.confidence >= 0.70
        assert o.estimated_net_value >= Decimal("0.00")
        assert o.status in ["GENERATED", "SIMULATED", "APPROVED", "EXECUTED"]

def test_3_inventory_risk_detection(db_session):
    """
    Validates detection of low-stock items (< 20 units).
    """
    merchant = db_session.query(Merchant).filter(Merchant.is_active == True).first()
    prod = db_session.query(Product).filter(Product.merchant_id == merchant.id).first()
    
    # Set low stock
    inv = prod.inventory
    if inv:
        inv.stock_quantity = 5
        db_session.commit()

    opps = RevenueOpportunityEngine.discover_opportunities(db_session, merchant.id, types=["INVENTORY_RISK"])
    assert any(o.type == "INVENTORY_RISK" for o in opps)

def test_4_merchant_opportunity_approval_and_execution(db_session):
    """
    Validates that merchant explicit approval updates status to APPROVED
    and execution transitions to EXECUTED.
    """
    merchant = db_session.query(Merchant).filter(Merchant.is_active == True).first()
    opps = RevenueOpportunityEngine.discover_opportunities(db_session, merchant.id)
    opp_id = opps[0].id
    db_session.commit()
    db_session.close()

    # Approve
    appr_res = client.post(f"/api/v1/revenue/opportunities/{opp_id}/approve", json={
        "reason": "Merchant admin approved bundle"
    })
    assert appr_res.status_code == 200
    assert appr_res.json()["status"] == "APPROVED"

    # Execute
    exec_res = client.post(f"/api/v1/revenue/opportunities/{opp_id}/execute", json={
        "idempotency_key": "idem_exec_opp_001"
    })
    assert exec_res.status_code == 200
    assert exec_res.json()["status"] == "EXECUTED"

def test_5_merchant_growth_copilot_conversational_intelligence(db_session):
    """
    Validates conversational Copilot queries with grounded database recommendations.
    """
    merchant = db_session.query(Merchant).filter(Merchant.is_active == True).first()
    
    # Query 1: Revenue optimization
    res1 = client.post("/api/v1/revenue/copilot/chat", json={
        "message": "What can I do right now to increase revenue?",
        "merchant_id": merchant.id
    })
    assert res1.status_code == 200
    data1 = res1.json()
    assert "reply" in data1
    assert "growth_overview" in data1
    assert "actionable_proposals" in data1

    # Query 2: Stockout risks
    res2 = client.post("/api/v1/revenue/copilot/chat", json={
        "message": "Which products are at risk of stockout?",
        "merchant_id": merchant.id
    })
    assert res2.status_code == 200
    assert "reply" in res2.json()

def test_6_merchant_tenant_isolation(db_session):
    """
    Ensures opportunities and metrics belonging to merchant A are never
    returned when querying merchant B.
    """
    merchants = db_session.query(Merchant).all()
    if len(merchants) >= 2:
        m1, m2 = merchants[0], merchants[1]
        opps1 = client.get(f"/api/v1/revenue/opportunities?merchant_id={m1.id}").json()
        opps2 = client.get(f"/api/v1/revenue/opportunities?merchant_id={m2.id}").json()

        ids1 = {o["id"] for o in opps1}
        ids2 = {o["id"] for o in opps2}
        assert ids1.isdisjoint(ids2)
