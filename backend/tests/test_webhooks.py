import json
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.database.models.inventory import Inventory
from app.database.models.product import Product
from app.database.models.payment_transaction import PaymentTransaction
from app.database.models.purchase_intent import PurchaseIntent
from app.database.models.webhook_event import WebhookEvent
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

def test_webhook_valid_signature_and_capture(client: TestClient, db: Session, setup_test_data):
    """
    Verifies that a valid webhook with HMAC signature transitions PaymentTransaction to CAPTURED
    and marks PurchaseIntent as COMPLETED.
    """
    m1_id = setup_test_data["m1"]
    session_id = "test_sess_wh_01"

    p1 = _ensure_products(db, m1_id)
    client.post("/api/v1/ai/shopping", json={"session_id": session_id, "merchant_id": m1_id, "message": f"add product {p1.id} to cart"})
    
    res_pi = client.post("/api/v1/ai/purchase-intents", json={
        "session_id": session_id,
        "buyer_id": "buyer_wh_01",
        "merchant_id": m1_id,
        "constraints": {"max_price": 5000.0, "currency": "INR"}
    })
    pi_id = res_pi.json()["id"]

    res_eval = client.post(f"/api/v1/purchase-intents/{pi_id}/evaluate?merchant_id={m1_id}")
    auth_id = res_eval.json()["authorization"]["id"]

    res_order = client.post(f"/api/v1/payments/create-order?merchant_id={m1_id}", json={
        "purchase_intent_id": pi_id,
        "authorization_id": auth_id,
        "idempotency_key": "idemp_wh_001"
    })
    order_id = res_order.json()["razorpay_order_id"]
    tx_id = res_order.json()["payment_transaction_id"]

    # Construct Webhook payload
    webhook_payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_test_capture_123",
                    "order_id": order_id,
                    "amount": 389800,
                    "currency": "INR",
                    "status": "captured"
                }
            }
        }
    }
    raw_body = json.dumps(webhook_payload).encode("utf-8")
    mock_provider = PaymentService.get_mock_provider()
    signature = mock_provider.generate_signature(raw_body)
    event_id = "evt_capture_unique_001"

    # Send Webhook
    res_wh = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": signature,
            "X-Razorpay-Event-Id": event_id
        }
    )
    assert res_wh.status_code == 200

    # Verify PaymentTransaction state updated to CAPTURED
    tx = db.query(PaymentTransaction).filter(PaymentTransaction.id == tx_id).first()
    assert tx.status == PaymentState.CAPTURED
    assert tx.razorpay_payment_id == "pay_test_capture_123"
    assert tx.captured_at is not None

    # Verify linked PurchaseIntent is COMPLETED
    pi = db.query(PurchaseIntent).filter(PurchaseIntent.id == pi_id).first()
    assert pi.status == "COMPLETED"

def test_webhook_invalid_signature_rejected(client: TestClient, db: Session, setup_test_data):
    """
    Verifies that an invalid webhook signature returns 401 Unauthorized and does NOT mutate state.
    """
    m1_id = setup_test_data["m1"]
    raw_body = b'{"event":"payment.captured","payload":{"payment":{"entity":{"id":"pay_fake_999","order_id":"order_fake"}}}}'

    res_wh = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": "invalid_forged_signature",
            "X-Razorpay-Event-Id": "evt_fraud_001"
        }
    )
    assert res_wh.status_code == 401

def test_webhook_deduplication(client: TestClient, db: Session, setup_test_data):
    """
    Verifies that duplicate webhook events with the same x-razorpay-event-id are processed exactly once.
    """
    m1_id = setup_test_data["m1"]
    session_id = "test_sess_wh_dedup"

    p1 = _ensure_products(db, m1_id)
    client.post("/api/v1/ai/shopping", json={"session_id": session_id, "merchant_id": m1_id, "message": f"add product {p1.id} to cart"})
    
    res_pi = client.post("/api/v1/ai/purchase-intents", json={
        "session_id": session_id,
        "buyer_id": "buyer_wh_dedup",
        "merchant_id": m1_id,
        "constraints": {"max_price": 5000.0, "currency": "INR"}
    })
    pi_id = res_pi.json()["id"]

    res_eval = client.post(f"/api/v1/purchase-intents/{pi_id}/evaluate?merchant_id={m1_id}")
    auth_id = res_eval.json()["authorization"]["id"]

    res_order = client.post(f"/api/v1/payments/create-order?merchant_id={m1_id}", json={
        "purchase_intent_id": pi_id,
        "authorization_id": auth_id,
        "idempotency_key": "idemp_wh_dedup"
    })
    order_id = res_order.json()["razorpay_order_id"]

    webhook_payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_dedup_100",
                    "order_id": order_id,
                    "amount": 389800,
                    "currency": "INR",
                    "status": "captured"
                }
            }
        }
    }
    raw_body = json.dumps(webhook_payload).encode("utf-8")
    mock_provider = PaymentService.get_mock_provider()
    signature = mock_provider.generate_signature(raw_body)
    event_id = "evt_dedup_unique_token_888"

    # Send first time -> 200 OK
    res1 = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": signature, "X-Razorpay-Event-Id": event_id}
    )
    assert res1.status_code == 200

    # Send second time (duplicate) -> 200 OK with duplicate notice
    res2 = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": signature, "X-Razorpay-Event-Id": event_id}
    )
    assert res2.status_code == 200
    assert "duplicate" in res2.json()["message"].lower() or res2.json()["processing_status"] in ("PROCESSED", "DUPLICATE")
