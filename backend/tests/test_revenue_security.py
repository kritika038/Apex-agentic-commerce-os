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

def test_revenue_tenant_isolation_and_security_guards(client, db):
    # Setup Merchant A and Merchant B
    mA = Merchant(name="Merchant A", domain="a.test", is_active=True)
    mB = Merchant(name="Merchant B", domain="b.test", is_active=True)
    db.add_all([mA, mB])
    db.commit()
    db.refresh(mA)
    db.refresh(mB)

    # Merchant A Opportunity
    oppA = RevenueOpportunity(
        merchant_id=mA.id,
        type="CROSS_SELL",
        title="Merchant A Secret Campaign",
        description="Exclusive to A",
        reason="Confidential",
        proposed_discount_percent=Decimal("5.00"),
        status="GENERATED"
    )
    db.add(oppA)
    db.commit()

    # 1. Merchant B queries Merchant A's opportunity -> 404
    res_cross = client.get(f"/api/v1/revenue/opportunities/{oppA.id}?merchant_id={mB.id}")
    assert res_cross.status_code == 404

    # 2. Merchant B attempts to approve Merchant A's opportunity -> 404
    res_cross_appr = client.post(f"/api/v1/revenue/opportunities/{oppA.id}/approve?merchant_id={mB.id}", json={
        "reason": "Unauthorized cross approval"
    })
    assert res_cross_appr.status_code == 404

    # 3. Execution blocked if target product became out-of-stock
    pA = Product(merchant_id=mA.id, name="Depleted Stock Item", price=Decimal("1000.00"), category="General", is_active=True)
    db.add(pA)
    db.flush()
    db.add(Inventory(merchant_id=mA.id, product_id=pA.id, stock_quantity=0)) # Stock is 0

    opp_oos = RevenueOpportunity(
        merchant_id=mA.id,
        type="CAMPAIGN",
        source_product_id=pA.id,
        target_product_ids=[pA.id],
        title="Out of stock campaign",
        description="Should fail execution",
        reason="Testing",
        proposed_discount_percent=Decimal("5.00"),
        status="APPROVED"
    )
    db.add(opp_oos)
    db.commit()

    res_exec_oos = client.post(f"/api/v1/revenue/opportunities/{opp_oos.id}/execute?merchant_id={mA.id}", json={
        "idempotency_key": "idemp_oos_test"
    })
    assert res_exec_oos.status_code == 400
    assert "is currently out of stock" in res_exec_oos.json()["detail"]
