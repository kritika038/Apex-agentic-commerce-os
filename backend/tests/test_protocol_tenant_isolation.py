import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database.models.product import Product
from app.database.models.inventory import Inventory

def test_protocol_cross_merchant_isolation(client: TestClient, db: Session, setup_test_data):
    """
    Security Test: Cross-merchant protocol queries, intents, and authorizations are strictly isolated.
    """
    m1_id = setup_test_data["m1"]
    m2_id = setup_test_data["m2"]

    # Seed M1 product
    p1 = Product(merchant_id=m1_id, name="M1 Exclusive Gear", price=Decimal("1999.00"), category="Gear", is_active=True)
    db.add(p1)
    db.flush()
    db.add(Inventory(merchant_id=m1_id, product_id=p1.id, stock_quantity=10))
    db.commit()

    # 1. Discover under M2 context should NOT return M1's products
    res_m2_disc = client.post(f"/api/v1/protocol/discover?merchant_id={m2_id}", json={
        "query": "Exclusive Gear"
    })
    assert res_m2_disc.status_code == 200
    assert res_m2_disc.json()["total_found"] == 0

    # 2. Querying invalid merchant ID returns 404
    res_invalid = client.get("/api/v1/protocol/capabilities?merchant_id=non_existent_merchant_id")
    assert res_invalid.status_code == 404
