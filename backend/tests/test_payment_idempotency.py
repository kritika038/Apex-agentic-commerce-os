from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.database.models.inventory import Inventory
from app.database.models.product import Product
from app.database.models.payment_transaction import PaymentTransaction

def _ensure_products(db: Session, merchant_id: str):
    p1 = db.query(Product).filter(Product.merchant_id == merchant_id, Product.name == "Pro Running Shoes").first()
    if not p1:
        p1 = Product(merchant_id=merchant_id, name="Pro Running Shoes", price=Decimal("3499.00"), category="Running", is_active=True)
        p2 = Product(merchant_id=merchant_id, name="Performance Socks", price=Decimal("399.00"), category="Accessories", is_active=True)
        db.add_all([p1, p2])
        db.flush()
        db.add(Inventory(merchant_id=merchant_id, product_id=p1.id, stock_quantity=20))
        db.add(Inventory(merchant_id=merchant_id, product_id=p2.id, stock_quantity=100))
        db.commit()
    return p1

def test_payment_creation_idempotency(client: TestClient, db: Session, setup_test_data):
    """
    Verifies that calling create-order with the same (merchant_id, idempotency_key)
    returns the existing transaction without generating a duplicate gateway order or database record.
    """
    m1_id = setup_test_data["m1"]
    session_id = "test_sess_idemp_01"

    p1 = _ensure_products(db, m1_id)
    client.post("/api/v1/ai/shopping", json={"session_id": session_id, "merchant_id": m1_id, "message": f"add product {p1.id} to cart"})
    
    res_pi = client.post("/api/v1/ai/purchase-intents", json={
        "session_id": session_id,
        "buyer_id": "buyer_idemp_01",
        "merchant_id": m1_id,
        "constraints": {"max_price": 5000.0, "currency": "INR"}
    })
    pi_id = res_pi.json()["id"]

    res_eval = client.post(f"/api/v1/purchase-intents/{pi_id}/evaluate?merchant_id={m1_id}")
    auth_id = res_eval.json()["authorization"]["id"]

    # Request 1: First order creation
    idemp_key = "idemp_unique_token_999"
    res1 = client.post(f"/api/v1/payments/create-order?merchant_id={m1_id}", json={
        "purchase_intent_id": pi_id,
        "authorization_id": auth_id,
        "idempotency_key": idemp_key
    })
    assert res1.status_code == 200
    data1 = res1.json()
    tx_id_1 = data1["payment_transaction_id"]
    order_id_1 = data1["razorpay_order_id"]

    # Request 2: Duplicate request with the identical idempotency key
    res2 = client.post(f"/api/v1/payments/create-order?merchant_id={m1_id}", json={
        "purchase_intent_id": pi_id,
        "authorization_id": auth_id,
        "idempotency_key": idemp_key
    })
    assert res2.status_code == 200
    data2 = res2.json()
    tx_id_2 = data2["payment_transaction_id"]
    order_id_2 = data2["razorpay_order_id"]

    # Exact equality: same transaction reused, no duplicate created
    assert tx_id_1 == tx_id_2
    assert order_id_1 == order_id_2

    # Verify only 1 PaymentTransaction exists in the DB for this idempotency key
    count = db.query(PaymentTransaction).filter(
        PaymentTransaction.merchant_id == m1_id,
        PaymentTransaction.idempotency_key == idemp_key
    ).count()
    assert count == 1
