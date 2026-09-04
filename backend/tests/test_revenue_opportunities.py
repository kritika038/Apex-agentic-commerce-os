import pytest
from decimal import Decimal
from fastapi.testclient import TestClient

from app.main import app
from app.database.models.merchant import Merchant
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.policy import Policy

client = TestClient(app)

def test_revenue_opportunity_generation_and_inventory_awareness(client, db):
    # Setup Merchant
    merchant = Merchant(name="Pro Runner Merchant", domain="runner.test", is_active=True)
    db.add(merchant)
    db.commit()
    db.refresh(merchant)

    # Setup Catalog: 1 Footwear, 1 Accessories, 1 Out of Stock
    p_shoes = Product(merchant_id=merchant.id, name="Speed Carbon Shoes", price=Decimal("4999.00"), category="Footwear", is_active=True)
    p_socks = Product(merchant_id=merchant.id, name="Pro Grip Socks", price=Decimal("499.00"), category="Accessories", is_active=True)
    p_oos = Product(merchant_id=merchant.id, name="Soldout Cap", price=Decimal("799.00"), category="Accessories", is_active=True)
    db.add_all([p_shoes, p_socks, p_oos])
    db.flush()

    db.add(Inventory(merchant_id=merchant.id, product_id=p_shoes.id, stock_quantity=15))
    db.add(Inventory(merchant_id=merchant.id, product_id=p_socks.id, stock_quantity=30))
    db.add(Inventory(merchant_id=merchant.id, product_id=p_oos.id, stock_quantity=0)) # Out of stock!
    db.commit()

    # Generate opportunities
    res = client.post(f"/api/v1/revenue/opportunities/generate?merchant_id={merchant.id}", json={
        "min_confidence": 0.70
    })
    assert res.status_code == 200
    opps = res.json()
    assert len(opps) > 0

    # Ensure out of stock item is never recommended
    for o in opps:
        assert p_oos.id not in o["target_product_ids"], "Out of stock item must never be recommended!"
        assert o["confidence"] >= 0.70

    # Retrieve single opportunity with AI proposal vs server authoritative breakdown
    opp_id = opps[0]["id"]
    res_single = client.get(f"/api/v1/revenue/opportunities/{opp_id}?merchant_id={merchant.id}")
    assert res_single.status_code == 200
    data = res_single.json()
    assert "opportunity" in data
    assert "proposal_breakdown" in data
    assert data["proposal_breakdown"]["server_authoritative_facts"]["authority_source"] == "SQL_DATABASE_DETERMINISTIC_CORE"
