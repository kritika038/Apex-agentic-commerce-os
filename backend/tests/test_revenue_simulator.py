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

def test_deterministic_revenue_simulator_and_policy_compliance(client, db):
    # Setup Merchant
    merchant = Merchant(name="Apex Fitness", domain="apex.test", is_active=True)
    db.add(merchant)
    db.commit()
    db.refresh(merchant)

    # Setup Policy with max_discount_percent = 5%
    policy = Policy(
        merchant_id=merchant.id,
        version=1,
        max_discount_percent=Decimal("5.00"),
        approval_threshold=Decimal("10000.00"),
        is_active=True
    )
    product = Product(merchant_id=merchant.id, name="Fitness Bands", price=Decimal("1000.00"), category="Equipment", is_active=True)
    db.add_all([policy, product])
    db.flush()

    db.add(Inventory(merchant_id=merchant.id, product_id=product.id, stock_quantity=100))
    opp = RevenueOpportunity(
        merchant_id=merchant.id,
        type="CAMPAIGN",
        source_product_id=product.id,
        target_product_ids=[product.id],
        title="Fitness Summer Campaign",
        description="Run 5% discount campaign on fitness bands.",
        reason="Seasonal demand peak.",
        proposed_discount_percent=Decimal("5.00"),
        estimated_incremental_orders=20,
        status="GENERATED"
    )
    db.add(opp)
    db.commit()

    # 1. Simulate with compliant 5% discount and 20 orders
    res_compliant = client.post(f"/api/v1/revenue/simulate?merchant_id={merchant.id}", json={
        "opportunity_id": opp.id,
        "discount_percent": 5.0,
        "target_orders": 20
    })
    assert res_compliant.status_code == 200
    data = res_compliant.json()
    assert data["is_simulated"] is True
    assert data["simulation_label"] == "SIMULATED — NOT ACTUAL REVENUE"
    assert data["policy_compliant"] is True
    # Incremental GMV = 20 * 1000 = 20,000. Discount Cost = 20,000 * 0.05 = 1,000. Net = 19,000.
    assert Decimal(str(data["incremental_gmv"])) == Decimal("20000.00")
    assert Decimal(str(data["discount_cost"])) == Decimal("1000.00")
    assert Decimal(str(data["net_incremental_value"])) == Decimal("19000.00")

    # 2. Simulate with non-compliant 15% discount (exceeds policy limit of 5%)
    res_non_compliant = client.post(f"/api/v1/revenue/simulate?merchant_id={merchant.id}", json={
        "opportunity_id": opp.id,
        "discount_percent": 15.0,
        "target_orders": 20
    })
    assert res_non_compliant.status_code == 200
    data_bad = res_non_compliant.json()
    assert data_bad["policy_compliant"] is False
    assert "POLICY VIOLATION" in data_bad["policy_check_details"]
    assert data_bad["risk_level"] == "HIGH"
