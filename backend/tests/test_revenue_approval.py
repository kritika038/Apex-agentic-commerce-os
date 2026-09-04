import pytest
from decimal import Decimal
from fastapi.testclient import TestClient

from app.main import app
from app.database.models.merchant import Merchant
from app.database.models.product import Product
from app.database.models.policy import Policy
from app.database.models.revenue_opportunity import RevenueOpportunity

client = TestClient(app)

def test_revenue_approval_and_rejection_workflow(client, db):
    merchant = Merchant(name="Zenith Athletics", domain="zenith.test", is_active=True)
    db.add(merchant)
    db.commit()
    db.refresh(merchant)

    policy = Policy(merchant_id=merchant.id, version=1, max_discount_percent=Decimal("5.00"), is_active=True)
    product = Product(merchant_id=merchant.id, name="Yoga Mat", price=Decimal("1500.00"), category="Fitness", is_active=True)
    db.add_all([policy, product])
    db.flush()

    opp_valid = RevenueOpportunity(
        merchant_id=merchant.id,
        type="CAMPAIGN",
        source_product_id=product.id,
        target_product_ids=[product.id],
        title="Yoga Mat Flash Sale",
        description="5% discount on yoga mats.",
        reason="Boost seasonal sales",
        proposed_discount_percent=Decimal("5.00"),
        status="SIMULATED"
    )
    opp_invalid = RevenueOpportunity(
        merchant_id=merchant.id,
        type="CAMPAIGN",
        source_product_id=product.id,
        target_product_ids=[product.id],
        title="Excessive Discount Sale",
        description="20% discount on yoga mats.",
        reason="Aggressive push",
        proposed_discount_percent=Decimal("20.00"), # Exceeds policy 5%
        status="SIMULATED"
    )
    db.add_all([opp_valid, opp_invalid])
    db.commit()

    # 1. Reject invalid approval attempt (violates policy)
    res_bad_appr = client.post(f"/api/v1/revenue/opportunities/{opp_invalid.id}/approve?merchant_id={merchant.id}", json={
        "reason": "Approving excessive discount"
    })
    assert res_bad_appr.status_code == 400
    assert "exceeds active policy maximum" in res_bad_appr.json()["detail"]

    # 2. Approve valid opportunity
    res_appr = client.post(f"/api/v1/revenue/opportunities/{opp_valid.id}/approve?merchant_id={merchant.id}", json={
        "reason": "Merchant approved campaign"
    })
    assert res_appr.status_code == 200
    assert res_appr.json()["status"] == "APPROVED"
    assert res_appr.json()["approved_by_user_id"] is not None

    # 3. Reject another opportunity with reason
    res_rej = client.post(f"/api/v1/revenue/opportunities/{opp_invalid.id}/reject?merchant_id={merchant.id}", json={
        "reason": "Exceeds margin threshold"
    })
    assert res_rej.status_code == 200
    assert res_rej.json()["status"] == "REJECTED"
    assert res_rej.json()["rejection_reason"] == "Exceeds margin threshold"
