import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.cart import Cart, CartItem
from app.database.models.recommendation import Recommendation
from app.agents.sales_agent import SalesAgent
from app.tools.shopping_tools import add_to_cart

def test_sales_agent_relevant_cross_sell(client: TestClient, db: Session, setup_test_data):
    m1_id = setup_test_data["m1"]
    session_id = "sess_rec_001"

    # Seed running shoes and socks
    p_shoes = Product(merchant_id=m1_id, name="Pro Running Shoes", price=Decimal("3499.00"), category="Running", is_active=True)
    p_socks = Product(merchant_id=m1_id, name="Performance Socks", price=Decimal("399.00"), category="Accessories", is_active=True)
    db.add_all([p_shoes, p_socks])
    db.flush()
    db.add(Inventory(merchant_id=m1_id, product_id=p_shoes.id, stock_quantity=10))
    db.add(Inventory(merchant_id=m1_id, product_id=p_socks.id, stock_quantity=50))
    db.commit()

    # Add shoes to cart
    add_to_cart(db=db, merchant_id=m1_id, session_id=session_id, product_id=p_shoes.id, quantity=1)

    # Sales Agent analyzes cart
    agent = SalesAgent(db=db, merchant_id=m1_id, session_id=session_id)
    recs = agent.generate_recommendations()

    assert len(recs) == 1
    assert recs[0].recommended_product_id == p_socks.id
    assert recs[0].type == "CROSS_SELL"
    assert Decimal(str(recs[0].product_price)) == Decimal("399.00")
    assert "complements" in recs[0].reason

def test_sales_agent_out_of_stock_not_recommended(db: Session, setup_test_data):
    m1_id = setup_test_data["m1"]
    session_id = "sess_oos_001"

    p_shoes = Product(merchant_id=m1_id, name="Pro Running Shoes", price=Decimal("3499.00"), category="Running", is_active=True)
    p_socks = Product(merchant_id=m1_id, name="Performance Socks", price=Decimal("399.00"), category="Accessories", is_active=True)
    db.add_all([p_shoes, p_socks])
    db.flush()
    db.add(Inventory(merchant_id=m1_id, product_id=p_shoes.id, stock_quantity=10))
    db.add(Inventory(merchant_id=m1_id, product_id=p_socks.id, stock_quantity=0)) # Out of stock!
    db.commit()

    add_to_cart(db=db, merchant_id=m1_id, session_id=session_id, product_id=p_shoes.id, quantity=1)

    agent = SalesAgent(db=db, merchant_id=m1_id, session_id=session_id)
    recs = agent.generate_recommendations()

    # Out of stock product must NOT be recommended
    rec_ids = [r.recommended_product_id for r in recs]
    assert p_socks.id not in rec_ids

def test_sales_agent_no_duplicate_or_in_cart_recommendation(db: Session, setup_test_data):
    m1_id = setup_test_data["m1"]
    session_id = "sess_dup_001"

    p_shoes = Product(merchant_id=m1_id, name="Pro Running Shoes", price=Decimal("3499.00"), category="Running", is_active=True)
    p_socks = Product(merchant_id=m1_id, name="Performance Socks", price=Decimal("399.00"), category="Accessories", is_active=True)
    db.add_all([p_shoes, p_socks])
    db.flush()
    db.add(Inventory(merchant_id=m1_id, product_id=p_shoes.id, stock_quantity=10))
    db.add(Inventory(merchant_id=m1_id, product_id=p_socks.id, stock_quantity=50))
    db.commit()

    # Case 1: Shoes and Socks already in cart -> no recommendation of socks
    add_to_cart(db=db, merchant_id=m1_id, session_id=session_id, product_id=p_shoes.id, quantity=1)
    add_to_cart(db=db, merchant_id=m1_id, session_id=session_id, product_id=p_socks.id, quantity=1)

    agent = SalesAgent(db=db, merchant_id=m1_id, session_id=session_id)
    recs = agent.generate_recommendations()
    assert len(recs) == 0

    # Case 2: In a new session, recommend once, second call should not duplicate
    session_2 = "sess_dup_002"
    add_to_cart(db=db, merchant_id=m1_id, session_id=session_2, product_id=p_shoes.id, quantity=1)
    agent2 = SalesAgent(db=db, merchant_id=m1_id, session_id=session_2)
    recs_first = agent2.generate_recommendations()
    assert len(recs_first) == 1

    recs_second = agent2.generate_recommendations()
    # Should not produce duplicate recommendations in same session
    assert len(recs_second) == 0

def test_recommendation_accept_and_reject_flow(client: TestClient, db: Session, setup_test_data):
    m1_id = setup_test_data["m1"]
    session_id = "sess_accept_001"

    p_shoes = Product(merchant_id=m1_id, name="Pro Running Shoes", price=Decimal("3499.00"), category="Running", is_active=True)
    p_socks = Product(merchant_id=m1_id, name="Performance Socks", price=Decimal("399.00"), category="Accessories", is_active=True)
    db.add_all([p_shoes, p_socks])
    db.flush()
    db.add(Inventory(merchant_id=m1_id, product_id=p_shoes.id, stock_quantity=10))
    db.add(Inventory(merchant_id=m1_id, product_id=p_socks.id, stock_quantity=50))
    db.commit()

    add_to_cart(db=db, merchant_id=m1_id, session_id=session_id, product_id=p_shoes.id, quantity=1)

    # 1. Trigger recommendations via API
    res_rec = client.post("/api/v1/ai/recommendations", json={"session_id": session_id, "message": "", "merchant_id": m1_id})
    assert res_rec.status_code == 200
    recs = res_rec.json()
    assert len(recs) == 1
    rec_id = recs[0]["id"]
    assert recs[0]["status"] == "SHOWN"

    # 2. Accept recommendation via API
    res_accept = client.post(f"/api/v1/ai/recommendations/{rec_id}/accept")
    assert res_accept.status_code == 200
    accept_data = res_accept.json()
    assert accept_data["success"] is True
    assert accept_data["status"] == "ACCEPTED"
    assert Decimal(str(accept_data["cart"]["total_amount"])) == Decimal("3898.00")
    assert len(accept_data["cart"]["items"]) == 2

    # 3. Create another recommendation in another session to test rejection
    session_3 = "sess_reject_001"
    add_to_cart(db=db, merchant_id=m1_id, session_id=session_3, product_id=p_shoes.id, quantity=1)
    res_rec3 = client.post("/api/v1/ai/recommendations", json={"session_id": session_3, "message": "", "merchant_id": m1_id})
    rec3_id = res_rec3.json()[0]["id"]

    res_reject = client.post(f"/api/v1/ai/recommendations/{rec3_id}/reject")
    assert res_reject.status_code == 200
    assert res_reject.json()["status"] == "REJECTED"

    # 4. Verify aggregated stats
    res_stats = client.get(f"/api/v1/ai/recommendations/stats/summary?merchant_id={m1_id}")
    assert res_stats.status_code == 200
    stats = res_stats.json()
    assert stats["total_recommendations"] == 2
    assert stats["accepted_count"] == 1
    assert stats["rejected_count"] == 1
    assert stats["acceptance_rate"] == 50.0
    assert Decimal(str(stats["additional_cart_value"])) == Decimal("399.00")
