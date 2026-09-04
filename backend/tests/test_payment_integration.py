import json
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.database.models.inventory import Inventory
from app.database.models.product import Product
from app.database.models.payment_transaction import PaymentTransaction
from app.database.models.purchase_intent import PurchaseIntent
from app.database.models.transaction_authorization import TransactionAuthorization
from app.payments.service import PaymentService
from app.payments.state_machine import PaymentState

def _ensure_products(db: Session, merchant_id: str):
    p_shoes = db.query(Product).filter(Product.merchant_id == merchant_id, Product.name == "Pro Running Shoes").first()
    if not p_shoes:
        p_shoes = Product(merchant_id=merchant_id, name="Pro Running Shoes", price=Decimal("3499.00"), category="Running", is_active=True)
        p_socks = Product(merchant_id=merchant_id, name="Performance Socks", price=Decimal("399.00"), category="Accessories", is_active=True)
        db.add_all([p_shoes, p_socks])
        db.flush()
        db.add(Inventory(merchant_id=merchant_id, product_id=p_shoes.id, stock_quantity=20))
        db.add(Inventory(merchant_id=merchant_id, product_id=p_socks.id, stock_quantity=100))
        db.commit()
    else:
        p_socks = db.query(Product).filter(Product.merchant_id == merchant_id, Product.name == "Performance Socks").first()
    return p_shoes, p_socks

def test_complete_payment_lifecycle_integration(client: TestClient, db: Session, setup_test_data):
    """
    Phase 5 Critical Integration Test:
    1. Create valid Phase 4 TransactionAuthorization.
    2. Create PaymentTransaction.
    3. Create Razorpay/Test Mock order.
    4. Simulate provider payment success.
    5. Process server-side provider/webhook result.
    6. Verify PaymentTransaction becomes CAPTURED.
    7. Verify PurchaseIntent/payment linkage remains consistent.
    """
    m1_id = setup_test_data["m1"]
    session_id = "test_sess_full_integration"

    # Step 1: AI Buyer creates cart with Shoes (₹3,499) + Socks (₹399) = ₹3,898
    p_shoes, p_socks = _ensure_products(db, m1_id)

    client.post("/api/v1/ai/shopping", json={"session_id": session_id, "merchant_id": m1_id, "message": f"add product {p_shoes.id} to cart"})
    client.post("/api/v1/ai/shopping", json={"session_id": session_id, "merchant_id": m1_id, "message": f"add product {p_socks.id} to cart"})

    # Step 2: Create Purchase Intent
    res_pi = client.post("/api/v1/ai/purchase-intents", json={
        "session_id": session_id,
        "buyer_id": "buyer_integration_01",
        "merchant_id": m1_id,
        "constraints": {"max_price": 4000.0, "currency": "INR", "quantity": 2}
    })
    assert res_pi.status_code == 200
    pi_data = res_pi.json()
    pi_id = pi_data["id"]
    assert Decimal(str(pi_data["requested_amount"])) == Decimal("3898.00")

    # Step 3: Evaluate Policy -> Obtain Valid TransactionAuthorization
    res_eval = client.post(f"/api/v1/purchase-intents/{pi_id}/evaluate?merchant_id={m1_id}")
    assert res_eval.status_code == 200
    eval_data = res_eval.json()
    assert eval_data["decision"] == "ALLOW"
    auth_data = eval_data["authorization"]
    auth_id = auth_data["id"]
    assert auth_data["status"] == "AUTHORIZED"
    assert Decimal(str(auth_data["authorized_amount"])) == Decimal("3898.00")

    # Step 4: Create Payment Order via PaymentService
    idemp_key = "idemp_integ_unique_777"
    res_order = client.post(f"/api/v1/payments/create-order?merchant_id={m1_id}", json={
        "purchase_intent_id": pi_id,
        "authorization_id": auth_id,
        "idempotency_key": idemp_key
    })
    assert res_order.status_code == 200
    order_data = res_order.json()
    tx_id = order_data["payment_transaction_id"]
    order_id = order_data["razorpay_order_id"]
    assert order_data["status"] == PaymentState.ORDER_CREATED
    assert Decimal(str(order_data["amount"])) == Decimal("3898.00")
    assert order_data["currency"] == "INR"

    # Step 5: Simulate gateway payment success & Webhook event
    webhook_payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_integ_settled_999",
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
    event_id = "evt_integ_settlement_001"

    # Step 6: Process server-side webhook
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

    # Step 7: Verify final database state and linkage integrity
    tx = db.query(PaymentTransaction).filter(PaymentTransaction.id == tx_id).first()
    assert tx.status == PaymentState.CAPTURED
    assert tx.razorpay_payment_id == "pay_integ_settled_999"
    assert tx.captured_at is not None
    assert tx.amount == Decimal("3898.00")
    assert tx.currency == "INR"
    assert tx.merchant_id == m1_id
    assert tx.purchase_intent_id == pi_id
    assert tx.authorization_id == auth_id

    # PurchaseIntent marked COMPLETED
    pi = db.query(PurchaseIntent).filter(PurchaseIntent.id == pi_id).first()
    assert pi.status == "COMPLETED"

    # Transaction Authorization remains intact
    auth = db.query(TransactionAuthorization).filter(TransactionAuthorization.id == auth_id).first()
    assert auth.status == "AUTHORIZED"
    assert auth.authorized_amount == Decimal("3898.00")

def test_payment_signature_verification_and_config(client: TestClient, db: Session, setup_test_data):
    """
    Verifies payment configuration endpoint and cryptographic signature verification flow.
    """
    m1_id = setup_test_data["m1"]
    session_id = "test_sess_sig_verify"

    # 1. Test /payments/config endpoint
    res_conf = client.get("/api/v1/payments/config")
    assert res_conf.status_code == 200
    conf = res_conf.json()
    assert "configured" in conf
    assert "mode" in conf
    assert "provider" in conf
    assert "currency" in conf

    # 2. Setup items and create order
    p_shoes, _ = _ensure_products(db, m1_id)
    client.post("/api/v1/ai/shopping", json={"session_id": session_id, "merchant_id": m1_id, "message": f"add product {p_shoes.id} to cart"})
    
    res_pi = client.post("/api/v1/ai/purchase-intents", json={
        "session_id": session_id,
        "buyer_id": "buyer_sig_01",
        "merchant_id": m1_id,
        "constraints": {"max_price": 5000.0, "currency": "INR"}
    })
    pi_id = res_pi.json()["id"]

    res_eval = client.post(f"/api/v1/purchase-intents/{pi_id}/evaluate?merchant_id={m1_id}")
    auth_id = res_eval.json()["authorization"]["id"]

    res_order = client.post(f"/api/v1/payments/create-order?merchant_id={m1_id}", json={
        "purchase_intent_id": pi_id,
        "authorization_id": auth_id,
        "idempotency_key": f"idemp_sig_{session_id}"
    })
    assert res_order.status_code == 200
    order_data = res_order.json()
    order_id = order_data["razorpay_order_id"]
    payment_id = "pay_test_sig_9999"

    # 3. Test Invalid Signature Rejection
    res_invalid_sig = client.post("/api/v1/payments/verify-signature", json={
        "razorpay_order_id": order_id,
        "razorpay_payment_id": payment_id,
        "razorpay_signature": "invalid_forged_signature_xyz"
    })
    assert res_invalid_sig.status_code == 400
    assert "signature verification failed" in res_invalid_sig.json()["detail"].lower()

    # 4. Test Valid Signature Verification
    valid_sig = f"sig_{order_id}_{payment_id}"
    res_valid_sig = client.post("/api/v1/payments/verify-signature", json={
        "razorpay_order_id": order_id,
        "razorpay_payment_id": payment_id,
        "razorpay_signature": valid_sig
    })
    assert res_valid_sig.status_code == 200
    tx_data = res_valid_sig.json()
    assert tx_data["status"] == PaymentState.CAPTURED
    assert tx_data["razorpay_payment_id"] == payment_id

    # 5. Test Idempotent Repeat Verification
    res_repeat = client.post("/api/v1/payments/verify-signature", json={
        "razorpay_order_id": order_id,
        "razorpay_payment_id": payment_id,
        "razorpay_signature": valid_sig
    })
    assert res_repeat.status_code == 200
    assert res_repeat.json()["status"] == PaymentState.CAPTURED

