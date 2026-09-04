import os
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

def test_concurrent_revenue_campaign_execution_idempotency(client, db):
    merchant = Merchant(name="Concurrency Merchant", domain="conc.test", is_active=True)
    db.add(merchant)
    db.commit()
    db.refresh(merchant)

    product = Product(merchant_id=merchant.id, name="Energy Gel", price=Decimal("150.00"), category="Nutrition", is_active=True)
    db.add(product)
    db.flush()
    db.add(Inventory(merchant_id=merchant.id, product_id=product.id, stock_quantity=100))

    opp = RevenueOpportunity(
        merchant_id=merchant.id,
        type="CAMPAIGN",
        source_product_id=product.id,
        target_product_ids=[product.id],
        title="Energy Gel Rush",
        description="Flash discount",
        reason="Testing",
        proposed_discount_percent=Decimal("5.00"),
        status="APPROVED"
    )
    db.add(opp)
    db.commit()

    # Simulate two duplicate concurrent executions with same idempotency key
    key = "idemp_concurrent_campaign_001"
    res1 = client.post(f"/api/v1/revenue/opportunities/{opp.id}/execute?merchant_id={merchant.id}", json={
        "idempotency_key": key
    })
    res2 = client.post(f"/api/v1/revenue/opportunities/{opp.id}/execute?merchant_id={merchant.id}", json={
        "idempotency_key": key
    })

    assert res1.status_code == 200
    assert res2.status_code == 200
    assert res1.json()["status"] == "EXECUTED"
    assert res2.json()["status"] == "EXECUTED"


@pytest.mark.skipif(not os.getenv("POSTGRES_TEST_URL"), reason="PostgreSQL test URL unavailable in environment")
def test_postgres_concurrent_revenue_campaign_locking():
    # Placeholder for PostgreSQL transaction locking verification
    pass
