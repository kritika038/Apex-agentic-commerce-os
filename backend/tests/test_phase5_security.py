from decimal import Decimal
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.database.models.inventory import Inventory
from app.database.models.product import Product
from app.database.models.merchant import Merchant
from app.database.models.transaction_authorization import TransactionAuthorization
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

def test_amount_tampering_rejected_before_provider_order(client: TestClient, db: Session, setup_test_data):
    """
    Security Test: Authorized amount is ₹3,499.00. Client attempts to specify ₹1.00.
    Server rejects the request before calling payment provider.
    """
    m1_id = setup_test_data["m1"]
    session_id = "test_sess_sec_amt_tamper"

    p1 = _ensure_products(db, m1_id)
    client.post("/api/v1/ai/shopping", json={"session_id": session_id, "merchant_id": m1_id, "message": f"add product {p1.id} to cart"})
    
    res_pi = client.post("/api/v1/ai/purchase-intents", json={
        "session_id": session_id,
        "buyer_id": "buyer_amt_tamper",
        "merchant_id": m1_id,
        "constraints": {"max_price": 5000.0, "currency": "INR"}
    })
    pi_id = res_pi.json()["id"]

    res_eval = client.post(f"/api/v1/purchase-intents/{pi_id}/evaluate?merchant_id={m1_id}")
    auth_id = res_eval.json()["authorization"]["id"]

    # Client specifies expected_amount = 1.0 (trying to charge ₹1 instead of ₹3,499)
    res_tamper = client.post(f"/api/v1/payments/create-order?merchant_id={m1_id}", json={
        "purchase_intent_id": pi_id,
        "authorization_id": auth_id,
        "idempotency_key": "idemp_sec_amt_tamper",
        "expected_amount": 1.0
    })
    assert res_tamper.status_code == 400
    assert "amount mismatch" in res_tamper.json()["detail"].lower()

def test_currency_tampering_rejected_before_provider_order(client: TestClient, db: Session, setup_test_data):
    """
    Security Test: Authorized currency is INR. Client attempts to specify USD.
    Server rejects the request before calling payment provider.
    """
    m1_id = setup_test_data["m1"]
    session_id = "test_sess_sec_curr_tamper"

    p1 = _ensure_products(db, m1_id)
    client.post("/api/v1/ai/shopping", json={"session_id": session_id, "merchant_id": m1_id, "message": f"add product {p1.id} to cart"})
    
    res_pi = client.post("/api/v1/ai/purchase-intents", json={
        "session_id": session_id,
        "buyer_id": "buyer_curr_tamper",
        "merchant_id": m1_id,
        "constraints": {"max_price": 5000.0, "currency": "INR"}
    })
    pi_id = res_pi.json()["id"]

    res_eval = client.post(f"/api/v1/purchase-intents/{pi_id}/evaluate?merchant_id={m1_id}")
    auth_id = res_eval.json()["authorization"]["id"]

    # Client specifies expected_currency = USD
    res_tamper = client.post(f"/api/v1/payments/create-order?merchant_id={m1_id}", json={
        "purchase_intent_id": pi_id,
        "authorization_id": auth_id,
        "idempotency_key": "idemp_sec_curr_tamper",
        "expected_currency": "USD"
    })
    assert res_tamper.status_code == 400
    assert "currency mismatch" in res_tamper.json()["detail"].lower()

def test_expired_authorization_cannot_create_payment(client: TestClient, db: Session, setup_test_data):
    """
    Security Test: Expired authorization cannot create a payment order.
    Blocked strictly before Razorpay API is called.
    """
    m1_id = setup_test_data["m1"]
    session_id = "test_sess_sec_exp"

    p1 = _ensure_products(db, m1_id)
    client.post("/api/v1/ai/shopping", json={"session_id": session_id, "merchant_id": m1_id, "message": f"add product {p1.id} to cart"})
    
    res_pi = client.post("/api/v1/ai/purchase-intents", json={
        "session_id": session_id,
        "buyer_id": "buyer_sec_exp",
        "merchant_id": m1_id,
        "constraints": {"max_price": 5000.0, "currency": "INR"}
    })
    pi_id = res_pi.json()["id"]

    res_eval = client.post(f"/api/v1/purchase-intents/{pi_id}/evaluate?merchant_id={m1_id}")
    auth_id = res_eval.json()["authorization"]["id"]

    # Manually expire the authorization
    auth = db.query(TransactionAuthorization).filter(TransactionAuthorization.id == auth_id).first()
    auth.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=5)
    db.commit()

    # Attempt payment creation
    res_pay = client.post(f"/api/v1/payments/create-order?merchant_id={m1_id}", json={
        "purchase_intent_id": pi_id,
        "authorization_id": auth_id,
        "idempotency_key": "idemp_sec_exp"
    })
    assert res_pay.status_code == 400
    assert "expired" in res_pay.json()["detail"].lower()

def test_cross_merchant_authorization_reuse_rejected(client: TestClient, db: Session, setup_test_data):
    """
    Security Test: Merchant 2 attempts to create an order using Merchant 1's authorization.
    Rejected by authorization validation.
    """
    m1_id = setup_test_data["m1"]
    m2_id = setup_test_data["m2"]
    session_id = "test_sess_sec_cross_auth"

    p1 = _ensure_products(db, m1_id)
    client.post("/api/v1/ai/shopping", json={"session_id": session_id, "merchant_id": m1_id, "message": f"add product {p1.id} to cart"})
    
    res_pi = client.post("/api/v1/ai/purchase-intents", json={
        "session_id": session_id,
        "buyer_id": "buyer_sec_cross_auth",
        "merchant_id": m1_id,
        "constraints": {"max_price": 5000.0, "currency": "INR"}
    })
    pi_id = res_pi.json()["id"]

    res_eval = client.post(f"/api/v1/purchase-intents/{pi_id}/evaluate?merchant_id={m1_id}")
    auth_id = res_eval.json()["authorization"]["id"]

    # Merchant 2 attempts to use Merchant 1's auth_id
    res_cross = client.post(f"/api/v1/payments/create-order?merchant_id={m2_id}", json={
        "purchase_intent_id": pi_id,
        "authorization_id": auth_id,
        "idempotency_key": "idemp_sec_cross_auth"
    })
    assert res_cross.status_code == 400
    assert "not found for this merchant" in res_cross.json()["detail"].lower()

def test_cross_merchant_payment_isolation(client: TestClient, db: Session, setup_test_data, auth_headers):
    """
    Security Test: Merchant 2 cannot access or view Merchant 1's payment transaction.
    """
    m1_id = setup_test_data["m1"]
    session_id = "test_sess_sec_cross"

    p1 = _ensure_products(db, m1_id)
    client.post("/api/v1/ai/shopping", json={"session_id": session_id, "merchant_id": m1_id, "message": f"add product {p1.id} to cart"})
    
    res_pi = client.post("/api/v1/ai/purchase-intents", json={
        "session_id": session_id,
        "buyer_id": "buyer_sec_cross",
        "merchant_id": m1_id,
        "constraints": {"max_price": 5000.0, "currency": "INR"}
    })
    pi_id = res_pi.json()["id"]

    res_eval = client.post(f"/api/v1/purchase-intents/{pi_id}/evaluate?merchant_id={m1_id}")
    auth_id = res_eval.json()["authorization"]["id"]

    res_order = client.post(f"/api/v1/payments/create-order?merchant_id={m1_id}", json={
        "purchase_intent_id": pi_id,
        "authorization_id": auth_id,
        "idempotency_key": "idemp_sec_cross"
    })
    tx_id = res_order.json()["payment_transaction_id"]

    # Merchant 2 (authenticated user u2) attempts to fetch Merchant 1's payment transaction
    headers2 = auth_headers("u2@m2.com")
    res_get_m2 = client.get(f"/api/v1/payments/{tx_id}", headers=headers2)
    assert res_get_m2.status_code == 404

def test_purchase_intent_mismatch_defense(client: TestClient, db: Session, setup_test_data):
    """
    Security Test: Attempting to create a payment order for Intent B using an Authorization bound to Intent A is rejected.
    """
    m1_id = setup_test_data["m1"]
    session_id = "test_sess_sec_mismatch"

    p1 = _ensure_products(db, m1_id)
    client.post("/api/v1/ai/shopping", json={"session_id": session_id, "merchant_id": m1_id, "message": f"add product {p1.id} to cart"})
    
    res_pi = client.post("/api/v1/ai/purchase-intents", json={
        "session_id": session_id,
        "buyer_id": "buyer_sec_mismatch",
        "merchant_id": m1_id,
        "constraints": {"max_price": 5000.0, "currency": "INR"}
    })
    pi_id = res_pi.json()["id"]

    res_eval = client.post(f"/api/v1/purchase-intents/{pi_id}/evaluate?merchant_id={m1_id}")
    auth_id = res_eval.json()["authorization"]["id"]

    # Attempt to use auth_id with a fake / different intent ID
    res_mismatch = client.post(f"/api/v1/payments/create-order?merchant_id={m1_id}", json={
        "purchase_intent_id": "fake_intent_999",
        "authorization_id": auth_id,
        "idempotency_key": "idemp_sec_mismatch"
    })
    assert res_mismatch.status_code == 400
    assert "mismatch" in res_mismatch.json()["detail"].lower()
