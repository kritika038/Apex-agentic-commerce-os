import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.audit_event import AuditEvent

def _seed_products(db: Session, merchant_id: str):
    p1 = db.query(Product).filter(Product.merchant_id == merchant_id, Product.name == "Pro Running Shoes").first()
    if not p1:
        p1 = Product(merchant_id=merchant_id, name="Pro Running Shoes", price=Decimal("3499.00"), category="Running", is_active=True)
        p2 = Product(merchant_id=merchant_id, name="Performance Socks", price=Decimal("399.00"), category="Accessories", is_active=True)
        p3 = Product(merchant_id=merchant_id, name="Heavy Boots", price=Decimal("7999.00"), category="Footwear", is_active=True)
        db.add_all([p1, p2, p3])
        db.flush()
        db.add(Inventory(merchant_id=merchant_id, product_id=p1.id, stock_quantity=15))
        db.add(Inventory(merchant_id=merchant_id, product_id=p2.id, stock_quantity=50))
        db.add(Inventory(merchant_id=merchant_id, product_id=p3.id, stock_quantity=0)) # out of stock
        db.commit()
    return p1

def test_protocol_discover_filters_and_price_grounding(client: TestClient, db: Session, setup_test_data):
    """
    Test: External AI agents can discover products within machine constraints.
    Prices and inventory originate from SQL database.
    """
    m1_id = setup_test_data["m1"]
    _seed_products(db, m1_id)
    trace_id = "trc_proto_disc_01"

    # Search with max_price = 4000
    res = client.post(f"/api/v1/protocol/discover?merchant_id={m1_id}", json={
        "query": "Running",
        "max_price": 4000.0,
        "currency": "INR",
        "trace_id": trace_id
    })
    assert res.status_code == 200
    data = res.json()

    assert data["trace_id"] == trace_id
    assert data["total_found"] >= 1
    
    # Verify products are <= 4000
    for p in data["products"]:
        assert float(p["price"]) <= 4000.0
        assert p["currency"] == "INR"

    # Verify audit event was logged
    ev = db.query(AuditEvent).filter(
        AuditEvent.merchant_id == m1_id,
        AuditEvent.trace_id == trace_id,
        AuditEvent.action == "PROTOCOL_DISCOVER"
    ).first()
    assert ev is not None

def test_protocol_recommend_flow(client: TestClient, db: Session, setup_test_data):
    """
    Test: External AI agent can query contextual recommendations for a session with cart items.
    """
    m1_id = setup_test_data["m1"]
    p1 = _seed_products(db, m1_id)
    session_id = "sess_proto_rec_01"
    trace_id = "trc_proto_rec_01"

    # 1. Add item to cart via shopping agent
    client.post("/api/v1/ai/shopping", json={
        "session_id": session_id,
        "merchant_id": m1_id,
        "message": f"add product {p1.id} to cart",
        "trace_id": trace_id
    })

    # 2. Call protocol recommend endpoint
    res_rec = client.post(f"/api/v1/protocol/recommend?merchant_id={m1_id}", json={
        "session_id": session_id,
        "trace_id": trace_id
    })
    assert res_rec.status_code == 200
    rec_data = res_rec.json()

    assert rec_data["session_id"] == session_id
    assert rec_data["trace_id"] == trace_id
    assert len(rec_data["recommendations"]) >= 1
    assert rec_data["recommendations"][0]["product_name"] == "Performance Socks"
