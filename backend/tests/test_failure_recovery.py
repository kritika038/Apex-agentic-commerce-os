import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.database.models.inventory import Inventory
from app.database.models.product import Product
from app.database.models.payment_transaction import PaymentTransaction
from app.database.models.payment_attempt import PaymentAttempt
from app.payments.service import PaymentService
from app.payments.reconciliation import PaymentReconciliation
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

def test_timeout_transitions_to_unknown_and_records_payment_attempt(client: TestClient, db: Session, setup_test_data):
    """
    Case A: Gateway timeout during order creation transitions PaymentTransaction to UNKNOWN
    and records an immutable PaymentAttempt with status TIMEOUT.
    """
    m1_id = setup_test_data["m1"]
    session_id = "sess_fr_timeout_01"

    p1 = _ensure_products(db, m1_id)
    client.post("/api/v1/ai/shopping", json={"session_id": session_id, "merchant_id": m1_id, "message": f"add product {p1.id} to cart"})
    
    res_pi = client.post("/api/v1/ai/purchase-intents", json={
        "session_id": session_id,
        "buyer_id": "buyer_fr_01",
        "merchant_id": m1_id,
        "constraints": {"max_price": 5000.0, "currency": "INR"}
    })
    pi_id = res_pi.json()["id"]
    res_eval = client.post(f"/api/v1/purchase-intents/{pi_id}/evaluate?merchant_id={m1_id}")
    auth_id = res_eval.json()["authorization"]["id"]

    mock_provider = PaymentService.get_mock_provider()
    mock_provider.set_mode("TIMEOUT")

    res_order = client.post(f"/api/v1/payments/create-order?merchant_id={m1_id}", json={
        "purchase_intent_id": pi_id,
        "authorization_id": auth_id,
        "idempotency_key": "idemp_fr_to_01"
    })
    assert res_order.status_code == 200
    tx_id = res_order.json()["payment_transaction_id"]

    tx = db.query(PaymentTransaction).filter(PaymentTransaction.id == tx_id).first()
    assert tx.status == PaymentState.UNKNOWN
    assert tx.failure_code == "GATEWAY_TIMEOUT"

    # Verify PaymentAttempt audit trail
    attempts = db.query(PaymentAttempt).filter(PaymentAttempt.payment_transaction_id == tx_id).all()
    assert len(attempts) >= 1
    assert attempts[0].status == "TIMEOUT"
    assert attempts[0].operation == "CREATE_ORDER"

    mock_provider.set_mode("SUCCESS")

def test_unknown_payment_blocks_new_order_creation_until_reconciled(client: TestClient, db: Session, setup_test_data):
    """
    CRITICAL INVARIANT (Correction 3):
    If a transaction is in UNKNOWN state, attempting to create a new order against the same authorization
    MUST be BLOCKED until reconciliation determines the provider-side state.
    """
    m1_id = setup_test_data["m1"]
    session_id = "sess_fr_block_01"

    p1 = _ensure_products(db, m1_id)
    client.post("/api/v1/ai/shopping", json={"session_id": session_id, "merchant_id": m1_id, "message": f"add product {p1.id} to cart"})
    
    res_pi = client.post("/api/v1/ai/purchase-intents", json={
        "session_id": session_id,
        "buyer_id": "buyer_fr_block",
        "merchant_id": m1_id,
        "constraints": {"max_price": 5000.0, "currency": "INR"}
    })
    pi_id = res_pi.json()["id"]
    res_eval = client.post(f"/api/v1/purchase-intents/{pi_id}/evaluate?merchant_id={m1_id}")
    auth_id = res_eval.json()["authorization"]["id"]

    mock_provider = PaymentService.get_mock_provider()
    mock_provider.set_mode("TIMEOUT")

    # First attempt: times out -> UNKNOWN
    res_order1 = client.post(f"/api/v1/payments/create-order?merchant_id={m1_id}", json={
        "purchase_intent_id": pi_id,
        "authorization_id": auth_id,
        "idempotency_key": "idemp_block_first"
    })
    tx1_id = res_order1.json()["payment_transaction_id"]
    tx1 = db.query(PaymentTransaction).filter(PaymentTransaction.id == tx1_id).first()
    assert tx1.status == PaymentState.UNKNOWN

    mock_provider.set_mode("SUCCESS")

    # Second attempt with new idempotency key on the same authorization: MUST BE BLOCKED (409)
    res_order2 = client.post(f"/api/v1/payments/create-order?merchant_id={m1_id}", json={
        "purchase_intent_id": pi_id,
        "authorization_id": auth_id,
        "idempotency_key": "idemp_block_second"
    })
    assert res_order2.status_code == 409
    assert "in unknown state" in res_order2.json()["detail"].lower()

def test_reconciliation_resolves_unknown_without_creating_second_order(client: TestClient, db: Session, setup_test_data):
    """
    Verifies that reconciliation queries the provider, transitions state to FAILED or CAPTURED,
    and NEVER creates a second payment order.
    """
    m1_id = setup_test_data["m1"]
    session_id = "sess_fr_recon_resolves"

    p1 = _ensure_products(db, m1_id)
    client.post("/api/v1/ai/shopping", json={"session_id": session_id, "merchant_id": m1_id, "message": f"add product {p1.id} to cart"})
    
    res_pi = client.post("/api/v1/ai/purchase-intents", json={
        "session_id": session_id,
        "buyer_id": "buyer_fr_recon",
        "merchant_id": m1_id,
        "constraints": {"max_price": 5000.0, "currency": "INR"}
    })
    pi_id = res_pi.json()["id"]
    res_eval = client.post(f"/api/v1/purchase-intents/{pi_id}/evaluate?merchant_id={m1_id}")
    auth_id = res_eval.json()["authorization"]["id"]

    mock_provider = PaymentService.get_mock_provider()
    mock_provider.set_mode("TIMEOUT")

    res_order = client.post(f"/api/v1/payments/create-order?merchant_id={m1_id}", json={
        "purchase_intent_id": pi_id,
        "authorization_id": auth_id,
        "idempotency_key": "idemp_recon_res_01"
    })
    tx_id = res_order.json()["payment_transaction_id"]

    mock_provider.set_mode("SUCCESS")

    # Reconcile the UNKNOWN transaction
    res_rec = client.post(f"/api/v1/payments/{tx_id}/reconcile?merchant_id={m1_id}")
    assert res_rec.status_code == 200

    tx = db.query(PaymentTransaction).filter(PaymentTransaction.id == tx_id).first()
    assert tx.status in (PaymentState.FAILED, PaymentState.CAPTURED, PaymentState.ORDER_CREATED)

    # Verify total transactions in DB for this authorization is still exactly 1
    total_tx_count = db.query(PaymentTransaction).filter(PaymentTransaction.authorization_id == auth_id).count()
    assert total_tx_count == 1
