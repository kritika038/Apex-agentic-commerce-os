from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.database.models.inventory import Inventory
from app.database.models.product import Product
from app.database.models.payment_transaction import PaymentTransaction
from app.database.models.reconciliation_attempt import ReconciliationAttempt
from app.payments.service import PaymentService
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

def test_payment_timeout_leads_to_unknown_and_reconciles(client: TestClient, db: Session, setup_test_data):
    """
    Verifies that a gateway timeout transitions the transaction to UNKNOWN
    and subsequent reconciliation recovers the state and creates a ReconciliationAttempt record.
    """
    m1_id = setup_test_data["m1"]
    session_id = "test_sess_recon_01"

    p1 = _ensure_products(db, m1_id)
    client.post("/api/v1/ai/shopping", json={"session_id": session_id, "merchant_id": m1_id, "message": f"add product {p1.id} to cart"})
    
    res_pi = client.post("/api/v1/ai/purchase-intents", json={
        "session_id": session_id,
        "buyer_id": "buyer_recon_01",
        "merchant_id": m1_id,
        "constraints": {"max_price": 5000.0, "currency": "INR"}
    })
    pi_id = res_pi.json()["id"]

    res_eval = client.post(f"/api/v1/purchase-intents/{pi_id}/evaluate?merchant_id={m1_id}")
    auth_id = res_eval.json()["authorization"]["id"]

    # 1. Simulate gateway timeout
    mock_provider = PaymentService.get_mock_provider()
    mock_provider.set_mode("TIMEOUT")

    res_order = client.post(f"/api/v1/payments/create-order?merchant_id={m1_id}", json={
        "purchase_intent_id": pi_id,
        "authorization_id": auth_id,
        "idempotency_key": "idemp_timeout_001"
    })
    assert res_order.status_code == 200
    tx_id = res_order.json()["payment_transaction_id"]

    # Verify transaction status is UNKNOWN
    tx = db.query(PaymentTransaction).filter(PaymentTransaction.id == tx_id).first()
    assert tx.status == PaymentState.UNKNOWN
    assert tx.failure_code == "GATEWAY_TIMEOUT"

    # 2. Simulate recovery / reconciliation
    mock_provider.set_mode("SUCCESS")
    res_recon = client.post(f"/api/v1/payments/{tx_id}/reconcile?merchant_id={m1_id}")
    assert res_recon.status_code == 200

    db.refresh(tx)
    assert tx.status in (PaymentState.FAILED, PaymentState.ORDER_CREATED, PaymentState.CAPTURED)

    # 3. Verify ReconciliationAttempt audit record created
    recons = db.query(ReconciliationAttempt).filter(
        ReconciliationAttempt.payment_transaction_id == tx_id
    ).all()
    assert len(recons) == 1
    assert recons[0].previous_status == PaymentState.UNKNOWN

def test_idempotent_duplicate_reconciliation(client: TestClient, db: Session, setup_test_data):
    """
    Verifies that running reconciliation multiple times is idempotent and safe.
    """
    m1_id = setup_test_data["m1"]
    session_id = "test_sess_recon_idemp"

    p1 = _ensure_products(db, m1_id)
    client.post("/api/v1/ai/shopping", json={"session_id": session_id, "merchant_id": m1_id, "message": f"add product {p1.id} to cart"})
    
    res_pi = client.post("/api/v1/ai/purchase-intents", json={
        "session_id": session_id,
        "buyer_id": "buyer_recon_idemp",
        "merchant_id": m1_id,
        "constraints": {"max_price": 5000.0, "currency": "INR"}
    })
    pi_id = res_pi.json()["id"]
    res_eval = client.post(f"/api/v1/purchase-intents/{pi_id}/evaluate?merchant_id={m1_id}")
    auth_id = res_eval.json()["authorization"]["id"]

    res_order = client.post(f"/api/v1/payments/create-order?merchant_id={m1_id}", json={
        "purchase_intent_id": pi_id,
        "authorization_id": auth_id,
        "idempotency_key": "idemp_recon_double"
    })
    tx_id = res_order.json()["payment_transaction_id"]

    # Reconcile first time
    res_recon1 = client.post(f"/api/v1/payments/{tx_id}/reconcile?merchant_id={m1_id}")
    assert res_recon1.status_code == 200
    status_1 = res_recon1.json()["current_status"]

    # Reconcile second time
    res_recon2 = client.post(f"/api/v1/payments/{tx_id}/reconcile?merchant_id={m1_id}")
    assert res_recon2.status_code == 200
    status_2 = res_recon2.json()["current_status"]
    assert status_1 == status_2

def test_cross_merchant_reconciliation_isolation(client: TestClient, db: Session, setup_test_data, auth_headers):
    """
    Security Test: Merchant 2 cannot reconcile Merchant 1's payment transaction.
    """
    m1_id = setup_test_data["m1"]
    session_id = "test_sess_recon_iso"

    p1 = _ensure_products(db, m1_id)
    client.post("/api/v1/ai/shopping", json={"session_id": session_id, "merchant_id": m1_id, "message": f"add product {p1.id} to cart"})
    
    res_pi = client.post("/api/v1/ai/purchase-intents", json={
        "session_id": session_id,
        "buyer_id": "buyer_recon_iso",
        "merchant_id": m1_id,
        "constraints": {"max_price": 5000.0, "currency": "INR"}
    })
    pi_id = res_pi.json()["id"]
    res_eval = client.post(f"/api/v1/purchase-intents/{pi_id}/evaluate?merchant_id={m1_id}")
    auth_id = res_eval.json()["authorization"]["id"]

    res_order = client.post(f"/api/v1/payments/create-order?merchant_id={m1_id}", json={
        "purchase_intent_id": pi_id,
        "authorization_id": auth_id,
        "idempotency_key": "idemp_recon_iso"
    })
    tx_id = res_order.json()["payment_transaction_id"]

    # Merchant 2 attempts to trigger reconciliation on Merchant 1's transaction
    headers2 = auth_headers("u2@m2.com")
    res_recon_m2 = client.post(f"/api/v1/payments/{tx_id}/reconcile", headers=headers2)
    assert res_recon_m2.status_code == 404
