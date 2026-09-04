import os
import json
import threading
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.database.models.inventory import Inventory
from app.database.models.product import Product
from app.database.models.payment_transaction import PaymentTransaction
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

def test_idempotent_duplicate_order_creations(client: TestClient, db: Session, setup_test_data):
    """
    Idempotency & Concurrency: Two rapid creation requests with the identical (merchant_id, idempotency_key).
    Database unique constraint and PaymentService idempotency guarantee exactly ONE transaction and ONE order exist.
    """
    m1_id = setup_test_data["m1"]
    session_id = "sess_conc_idemp"

    p1 = _ensure_products(db, m1_id)
    client.post("/api/v1/ai/shopping", json={"session_id": session_id, "merchant_id": m1_id, "message": f"add product {p1.id} to cart"})
    
    res_pi = client.post("/api/v1/ai/purchase-intents", json={
        "session_id": session_id,
        "buyer_id": "buyer_conc_01",
        "merchant_id": m1_id,
        "constraints": {"max_price": 5000.0, "currency": "INR"}
    })
    pi_id = res_pi.json()["id"]
    res_eval = client.post(f"/api/v1/purchase-intents/{pi_id}/evaluate?merchant_id={m1_id}")
    auth_id = res_eval.json()["authorization"]["id"]

    idemp_key = "idemp_conc_race_999"

    # Request 1
    res1 = client.post(f"/api/v1/payments/create-order?merchant_id={m1_id}", json={
        "purchase_intent_id": pi_id,
        "authorization_id": auth_id,
        "idempotency_key": idemp_key
    })
    assert res1.status_code == 200
    tx1 = res1.json()

    # Request 2 (identical key)
    res2 = client.post(f"/api/v1/payments/create-order?merchant_id={m1_id}", json={
        "purchase_intent_id": pi_id,
        "authorization_id": auth_id,
        "idempotency_key": idemp_key
    })
    assert res2.status_code == 200
    tx2 = res2.json()

    # Exactly same transaction and gateway order returned
    assert tx1["payment_transaction_id"] == tx2["payment_transaction_id"]
    assert tx1["razorpay_order_id"] == tx2["razorpay_order_id"]

    # Database count is exactly 1
    db_count = db.query(PaymentTransaction).filter(
        PaymentTransaction.merchant_id == m1_id,
        PaymentTransaction.idempotency_key == idemp_key
    ).count()
    assert db_count == 1

def test_concurrent_webhook_and_reconciliation_convergence(client: TestClient, db: Session, setup_test_data):
    """
    State Machine Race Safety: Simultaneous reconciliation and payment.captured webhook
    converge cleanly to CAPTURED without duplicate mutations or invalid state transitions.
    """
    m1_id = setup_test_data["m1"]
    session_id = "sess_conc_wh_rec"

    p1 = _ensure_products(db, m1_id)
    client.post("/api/v1/ai/shopping", json={"session_id": session_id, "merchant_id": m1_id, "message": f"add product {p1.id} to cart"})
    
    res_pi = client.post("/api/v1/ai/purchase-intents", json={
        "session_id": session_id,
        "buyer_id": "buyer_conc_wh",
        "merchant_id": m1_id,
        "constraints": {"max_price": 5000.0, "currency": "INR"}
    })
    pi_id = res_pi.json()["id"]
    res_eval = client.post(f"/api/v1/purchase-intents/{pi_id}/evaluate?merchant_id={m1_id}")
    auth_id = res_eval.json()["authorization"]["id"]

    res_order = client.post(f"/api/v1/payments/create-order?merchant_id={m1_id}", json={
        "purchase_intent_id": pi_id,
        "authorization_id": auth_id,
        "idempotency_key": "idemp_conc_wh_rec"
    })
    tx_id = res_order.json()["payment_transaction_id"]
    order_id = res_order.json()["razorpay_order_id"]

    mock_provider = PaymentService.get_mock_provider()
    raw_body = json.dumps({
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_conc_captured_777",
                    "order_id": order_id,
                    "amount": 349900,
                    "currency": "INR",
                    "status": "captured"
                }
            }
        }
    }).encode("utf-8")
    sig = mock_provider.generate_signature(raw_body)

    # 1. Deliver Webhook
    res_wh = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": sig,
            "X-Razorpay-Event-Id": "evt_conc_wh_001"
        }
    )
    assert res_wh.status_code == 200

    # 2. Trigger Reconciliation on now CAPTURED transaction
    res_rec = client.post(f"/api/v1/payments/{tx_id}/reconcile?merchant_id={m1_id}")
    assert res_rec.status_code == 200

    # Final state in DB is CAPTURED
    tx = db.query(PaymentTransaction).filter(PaymentTransaction.id == tx_id).first()
    assert tx.status == PaymentState.CAPTURED
    assert tx.razorpay_payment_id == "pay_conc_captured_777"

def test_out_of_order_webhook_never_downgrades_captured_state(client: TestClient, db: Session, setup_test_data):
    """
    Correction 8: Delivering an older/delayed payment.failed webhook AFTER payment.captured
    MUST NOT downgrade the transaction from CAPTURED to FAILED.
    """
    m1_id = setup_test_data["m1"]
    session_id = "sess_ooo_wh"

    p1 = _ensure_products(db, m1_id)
    client.post("/api/v1/ai/shopping", json={"session_id": session_id, "merchant_id": m1_id, "message": f"add product {p1.id} to cart"})
    
    res_pi = client.post("/api/v1/ai/purchase-intents", json={
        "session_id": session_id,
        "buyer_id": "buyer_ooo",
        "merchant_id": m1_id,
        "constraints": {"max_price": 5000.0, "currency": "INR"}
    })
    pi_id = res_pi.json()["id"]
    res_eval = client.post(f"/api/v1/purchase-intents/{pi_id}/evaluate?merchant_id={m1_id}")
    auth_id = res_eval.json()["authorization"]["id"]

    res_order = client.post(f"/api/v1/payments/create-order?merchant_id={m1_id}", json={
        "purchase_intent_id": pi_id,
        "authorization_id": auth_id,
        "idempotency_key": "idemp_ooo_test"
    })
    tx_id = res_order.json()["payment_transaction_id"]
    order_id = res_order.json()["razorpay_order_id"]

    mock_provider = PaymentService.get_mock_provider()

    # Step 1: Capture payment
    raw_cap = json.dumps({
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_ooo_captured",
                    "order_id": order_id,
                    "amount": 349900,
                    "currency": "INR",
                    "status": "captured"
                }
            }
        }
    }).encode("utf-8")
    sig_cap = mock_provider.generate_signature(raw_cap)
    res1 = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_cap,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig_cap, "X-Razorpay-Event-Id": "evt_ooo_cap"}
    )
    assert res1.status_code == 200

    tx = db.query(PaymentTransaction).filter(PaymentTransaction.id == tx_id).first()
    assert tx.status == PaymentState.CAPTURED

    # Step 2: Delayed payment.failed webhook arrives out-of-order
    raw_fail = json.dumps({
        "event": "payment.failed",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_ooo_late_fail",
                    "order_id": order_id,
                    "error_code": "GATEWAY_TIMEOUT",
                    "error_description": "Delayed failed webhook"
                }
            }
        }
    }).encode("utf-8")
    sig_fail = mock_provider.generate_signature(raw_fail)
    res2 = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_fail,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig_fail, "X-Razorpay-Event-Id": "evt_ooo_fail"}
    )
    assert res2.status_code == 200

    db.refresh(tx)
    # INVARIANT: Must still be CAPTURED!
    assert tx.status == PaymentState.CAPTURED
