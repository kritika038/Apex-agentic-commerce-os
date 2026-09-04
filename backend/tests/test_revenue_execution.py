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

def test_revenue_execution_prevalidation_and_idempotency(client, db):
    merchant = Merchant(name="Pulse Gear", domain="pulse.test", is_active=True)
    db.add(merchant)
    db.commit()
    db.refresh(merchant)

    policy = Policy(merchant_id=merchant.id, version=1, max_discount_percent=Decimal("5.00"), is_active=True)
    product = Product(merchant_id=merchant.id, name="Smart Bottle", price=Decimal("2000.00"), category="Accessories", is_active=True)
    db.add_all([policy, product])
    db.flush()

    inv = Inventory(merchant_id=merchant.id, product_id=product.id, stock_quantity=50)
    db.add(inv)

    opp = RevenueOpportunity(
        merchant_id=merchant.id,
        type="CAMPAIGN",
        source_product_id=product.id,
        target_product_ids=[product.id],
        title="Hydration Flash Deal",
        description="5% discount on Smart Bottles.",
        reason="Promote hydration awareness",
        proposed_discount_percent=Decimal("5.00"),
        estimated_incremental_orders=10,
        estimated_incremental_gmv=Decimal("20000.00"),
        estimated_discount_cost=Decimal("1000.00"),
        estimated_net_value=Decimal("19000.00"),
        status="APPROVED"
    )
    db.add(opp)
    db.commit()

    # 1. Successful execution
    res_exec = client.post(f"/api/v1/revenue/opportunities/{opp.id}/execute?merchant_id={merchant.id}", json={
        "idempotency_key": "idemp_exec_pulse_001"
    })
    assert res_exec.status_code == 200
    assert res_exec.json()["status"] == "EXECUTED"
    assert res_exec.json()["executed_at"] is not None

    # 2. Safe idempotent replay
    res_replay = client.post(f"/api/v1/revenue/opportunities/{opp.id}/execute?merchant_id={merchant.id}", json={
        "idempotency_key": "idemp_exec_pulse_001"
    })
    assert res_replay.status_code == 200
    assert res_replay.json()["status"] == "EXECUTED"

    # 3. Verify metrics and experiments
    res_metrics = client.get(f"/api/v1/revenue/metrics?merchant_id={merchant.id}")
    assert res_metrics.status_code == 200
    m_data = res_metrics.json()
    assert m_data["executed_campaigns"] == 1
    assert Decimal(str(m_data["actual_incremental_gmv"])) == Decimal("19000.00")

    res_exp = client.get(f"/api/v1/revenue/experiments?merchant_id={merchant.id}")
    assert res_exp.status_code == 200
    assert len(res_exp.json()) >= 1
    assert res_exp.json()[0]["status"] == "EXECUTED"
