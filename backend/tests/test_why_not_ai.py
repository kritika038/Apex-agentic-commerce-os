import pytest
from decimal import Decimal
from fastapi.testclient import TestClient

from app.main import app
from app.database.models.merchant import Merchant
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.policy import Policy
from app.database.models.revenue_opportunity import RevenueOpportunity

client = TestClient(app)

def test_why_not_ai_policy_block_and_separation_of_authority(client, db):
    """
    Validates that:
    1. AI can propose a creative marketing discount (e.g. 23%).
    2. Deterministic Policy Engine strictly enforces policy limits (max allowed: 5%).
    3. The proposal is marked non-compliant and cannot be approved.
    4. Proves: Autonomous AI reasoning does not equal financial authority.
    """
    merchant = Merchant(name="WhyNotAI Merchant", domain="whynotai.test", is_active=True)
    db.add(merchant)
    db.commit()
    db.refresh(merchant)

    policy = Policy(
        merchant_id=merchant.id,
        version=1,
        max_discount_percent=Decimal("5.00"),
        approval_threshold=Decimal("5000.00"),
        is_active=True
    )
    product = Product(merchant_id=merchant.id, name="Compression Sleeves", price=Decimal("1200.00"), category="Apparel", is_active=True)
    db.add_all([policy, product])
    db.flush()
    db.add(Inventory(merchant_id=merchant.id, product_id=product.id, stock_quantity=40))

    # AI creates an aggressive 23% discount proposal
    opp = RevenueOpportunity(
        merchant_id=merchant.id,
        type="CAMPAIGN",
        source_product_id=product.id,
        target_product_ids=[product.id],
        title="Aggressive Summer Clearance",
        description="AI proposes 23% discount to rapidly clear inventory.",
        reason="Maximize short term volume",
        proposed_discount_percent=Decimal("23.00"),
        estimated_incremental_orders=30,
        status="GENERATED"
    )
    db.add(opp)
    db.commit()

    # 1. Simulate the 23% discount proposal
    res_sim = client.post(f"/api/v1/revenue/simulate?merchant_id={merchant.id}", json={
        "opportunity_id": opp.id,
        "discount_percent": 23.0
    })
    assert res_sim.status_code == 200
    sim_data = res_sim.json()
    assert sim_data["policy_compliant"] is False
    assert "exceeds maximum permitted policy threshold of 5.00%" in sim_data["policy_check_details"]
    assert sim_data["risk_level"] == "HIGH"

    # 2. Attempt to approve 23% discount proposal -> Blocked with HTTP 400
    res_appr = client.post(f"/api/v1/revenue/opportunities/{opp.id}/approve?merchant_id={merchant.id}", json={
        "reason": "Trying to bypass policy"
    })
    assert res_appr.status_code == 400
    assert "exceeds active policy maximum" in res_appr.json()["detail"]

    # 3. Retrieve proposal breakdown to confirm clear separation of AI Proposal vs Server Facts
    res_get = client.get(f"/api/v1/revenue/opportunities/{opp.id}?merchant_id={merchant.id}")
    assert res_get.status_code == 200
    facts = res_get.json()["proposal_breakdown"]["server_authoritative_facts"]
    assert facts["proposed_discount"] == "23.00%"
    assert facts["policy_max_discount"] == "5.00%"
    assert facts["policy_compliant"] is False
    assert facts["authority_source"] == "SQL_DATABASE_DETERMINISTIC_CORE"
