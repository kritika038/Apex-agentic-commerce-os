import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.user import User
from app.database.models.purchase_intent import PurchaseIntent
from app.database.models.payment_transaction import PaymentTransaction
from app.tools.shopping_tools import add_to_cart

def test_unauthenticated_orders_me_rejected(client: TestClient):
    response = client.get("/api/v1/orders/me")
    assert response.status_code == 401

def test_empty_orders_returns_empty_list(client: TestClient, db: Session, setup_test_data):
    # Customer login
    login_res = client.post("/api/v1/auth/dev-login", json={"role": "customer"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/orders/me", headers=headers)
    assert response.status_code == 200
    assert response.json() == []

def test_customer_retrieves_own_orders_with_snapshot_integrity(client: TestClient, db: Session, setup_test_data):
    m1_id = setup_test_data["m1"]
    
    # 1. Customer login
    login_res = client.post("/api/v1/auth/dev-login", json={"role": "customer"})
    token = login_res.json()["access_token"]
    customer_email = login_res.json()["user"]["email"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Setup product: Shoes initially at ₹2,999
    p1 = Product(merchant_id=m1_id, name="Apex Marathon Shoes", price=Decimal("2999.00"), category="Running", is_active=True)
    db.add(p1)
    db.flush()
    db.add(Inventory(merchant_id=m1_id, product_id=p1.id, stock_quantity=20))
    db.commit()

    # 3. Add to cart & Create Purchase Intent with Delivery Address
    session_id = "sess_order_test_01"
    add_to_cart(db=db, merchant_id=m1_id, session_id=session_id, product_id=p1.id, quantity=1)

    addr = {
        "full_name": "Kritika Bansal",
        "phone": "9876543210",
        "email": customer_email,
        "address_line1": "Flat 402, Lotus Heights",
        "city": "Bengaluru",
        "state": "Karnataka",
        "pin_code": "560001",
        "country": "India"
    }

    intent_res = client.post("/api/v1/purchase-intents/", json={
        "session_id": session_id,
        "buyer_id": customer_email,
        "merchant_id": m1_id,
        "delivery_address": addr
    })
    assert intent_res.status_code == 200
    intent_id = intent_res.json()["id"]

    # 4. Evaluate and Create Order
    eval_res = client.post(f"/api/v1/purchase-intents/{intent_id}/evaluate")
    auth_id = eval_res.json()["authorization"]["id"]

    order_res = client.post("/api/v1/payments/create-order", json={
        "purchase_intent_id": intent_id,
        "authorization_id": auth_id,
        "idempotency_key": "idemp_order_test_01"
    })
    assert order_res.status_code == 200
    tx_id = order_res.json()["payment_transaction_id"]

    # 5. Simulate payment verification
    tx = db.query(PaymentTransaction).filter(PaymentTransaction.id == tx_id).first()
    tx.status = "CAPTURED"
    tx.razorpay_payment_id = "pay_test_verified_123"
    db.commit()

    # 6. Reprice product in catalog to ₹3,499 (price increased!)
    p1.price = Decimal("3499.00")
    db.commit()

    # 7. Query /orders/me
    orders_res = client.get("/api/v1/orders/me", headers=headers)
    assert orders_res.status_code == 200
    orders = orders_res.json()
    assert len(orders) >= 1

    my_order = next(o for o in orders if o["id"] == tx_id)
    assert my_order["status"] == "CONFIRMED"
    assert my_order["payment"]["status"] == "VERIFIED"
    assert my_order["payment"]["razorpay_payment_id"] == "pay_test_verified_123"
    
    # Verify Historical Price Snapshot: Still ₹2,999 (not ₹3,499)
    assert Decimal(str(my_order["total_amount"])) == Decimal("2999.00")
    assert Decimal(str(my_order["items"][0]["unit_price"])) == Decimal("2999.00")

    # Verify Historical Delivery Address Snapshot
    assert my_order["delivery_address"]["full_name"] == "Kritika Bansal"
    assert my_order["delivery_address"]["pin_code"] == "560001"

    # 8. Test "Buy Again": Must add item at CURRENT price ₹3,499
    new_sess = "sess_buy_again_cart"
    buy_again_res = client.post(
        f"/api/v1/orders/{tx_id}/buy-again",
        json={"session_id": new_sess},
        headers=headers
    )
    assert buy_again_res.status_code == 200
    ba_data = buy_again_res.json()
    assert ba_data["success"] is True
    assert len(ba_data["added_items"]) == 1
    assert ba_data["added_items"][0]["current_price"] == 3499.0
    assert ba_data["added_items"][0]["historical_price"] == 2999.0

def test_customer_cannot_view_another_customer_order(client: TestClient, db: Session, setup_test_data):
    m1_id = setup_test_data["m1"]

    # Customer A creates order
    login_a = client.post("/api/v1/auth/dev-login", json={"role": "customer"})
    token_a = login_a.json()["access_token"]
    email_a = login_a.json()["user"]["email"]

    p = Product(merchant_id=m1_id, name="Test Gear", price=Decimal("999.00"), category="Gear", is_active=True)
    db.add(p)
    db.flush()
    db.add(Inventory(merchant_id=m1_id, product_id=p.id, stock_quantity=10))
    db.commit()

    sess_a = "sess_cust_a"
    add_to_cart(db=db, merchant_id=m1_id, session_id=sess_a, product_id=p.id, quantity=1)

    intent_res = client.post("/api/v1/purchase-intents/", json={
        "session_id": sess_a,
        "buyer_id": email_a,
        "merchant_id": m1_id,
        "delivery_address": {"full_name": "Customer A", "phone": "9876543210", "email": email_a, "address_line1": "A Street", "city": "A City", "state": "State", "pin_code": "123456", "country": "India"}
    })
    intent_id = intent_res.json()["id"]
    eval_res = client.post(f"/api/v1/purchase-intents/{intent_id}/evaluate")
    auth_id = eval_res.json()["authorization"]["id"]

    order_res = client.post("/api/v1/payments/create-order", json={
        "purchase_intent_id": intent_id,
        "authorization_id": auth_id,
        "idempotency_key": "idemp_cust_a_order"
    })
    order_id = order_res.json()["payment_transaction_id"]

    # Customer B attempts to access Customer A's order
    register_b = client.post("/api/v1/auth/register", json={
        "email": "customer_b@example.com",
        "password": "password123",
        "full_name": "Customer B"
    })
    token_b = register_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    forbidden_res = client.get(f"/api/v1/orders/{order_id}", headers=headers_b)
    assert forbidden_res.status_code == 403
    assert "not authorized" in forbidden_res.json()["detail"]
