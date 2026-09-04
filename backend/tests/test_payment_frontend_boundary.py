from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.database.models.inventory import Inventory
from app.database.models.product import Product
from app.database.models.transaction_authorization import TransactionAuthorization
from app.database.models.payment_transaction import PaymentTransaction
from app.payments.state_machine import PaymentState

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

def test_frontend_cannot_directly_mutate_payment_status(client: TestClient, db: Session, setup_test_data):
    """
    Security Test: Frontend or client cannot submit status: CAPTURED or payment_status: success
    to directly mutate a PaymentTransaction. The backend server remains the sole authority.
    """
    m1_id = setup_test_data["m1"]
    session_id = "test_sess_fb_01"

    p1 = _ensure_products(db, m1_id)
    client.post("/api/v1/ai/shopping", json={"session_id": session_id, "merchant_id": m1_id, "message": f"add product {p1.id} to cart"})
    
    # Create Purchase Intent
    res_pi = client.post("/api/v1/ai/purchase-intents", json={
        "session_id": session_id,
        "buyer_id": "buyer_fb_01",
        "merchant_id": m1_id,
        "constraints": {"max_price": 5000.0, "currency": "INR"}
    })
    pi_id = res_pi.json()["id"]

    # Evaluate Policy to get Authorization
    res_eval = client.post(f"/api/v1/purchase-intents/{pi_id}/evaluate?merchant_id={m1_id}")
    auth_id = res_eval.json()["authorization"]["id"]

    # Create Payment Order
    res_order = client.post(f"/api/v1/payments/create-order?merchant_id={m1_id}", json={
        "purchase_intent_id": pi_id,
        "authorization_id": auth_id,
        "idempotency_key": "idemp_fb_001"
    })
    assert res_order.status_code == 200
    tx_id = res_order.json()["payment_transaction_id"]

    # Verify initial status is ORDER_CREATED
    tx = db.query(PaymentTransaction).filter(PaymentTransaction.id == tx_id).first()
    assert tx.status == PaymentState.ORDER_CREATED

    # Attack 1: Client attempts PUT /api/v1/payments/{tx_id} with {"status": "CAPTURED"}
    res_attack1 = client.put(f"/api/v1/payments/{tx_id}", json={"status": "CAPTURED"})
    assert res_attack1.status_code in (404, 405, 422)

    # Attack 2: Client attempts PATCH /api/v1/payments/{tx_id} with {"payment_status": "success"}
    res_attack2 = client.patch(f"/api/v1/payments/{tx_id}", json={"payment_status": "success", "status": "CAPTURED"})
    assert res_attack2.status_code in (404, 405, 422)

    # Attack 3: Client attempts POST /api/v1/payments/{tx_id}/capture directly
    res_attack3 = client.post(f"/api/v1/payments/{tx_id}/capture", json={"status": "CAPTURED"})
    assert res_attack3.status_code in (404, 405)

    # Verify in DB: Status remains strictly ORDER_CREATED and did not change
    db.refresh(tx)
    assert tx.status == PaymentState.ORDER_CREATED
    assert tx.captured_at is None
