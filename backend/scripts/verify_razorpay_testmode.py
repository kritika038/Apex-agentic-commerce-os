import sys
import os
import json
from decimal import Decimal
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.main import app
from app.database.session import SessionLocal
from app.database.models.product import Product
from app.database.models.merchant import Merchant
from app.database.models.payment_transaction import PaymentTransaction
from app.database.models.purchase_intent import PurchaseIntent
from app.database.models.transaction_authorization import TransactionAuthorization
from app.payments.razorpay_provider import RazorpayProvider
from app.payments.service import PaymentService
from app.payments.state_machine import PaymentState
from scripts.seed import seed_db

def verify_razorpay_gate():
    print("==========================================================================================")
    print(" PHASE 5 FINAL GATE — RAZORPAY TEST MODE & MOCK VERIFICATION")
    print("==========================================================================================\n")

    key_id = os.environ.get("RAZORPAY_KEY_ID", "")
    key_secret = os.environ.get("RAZORPAY_KEY_SECRET", "")
    webhook_secret = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "test_webhook_secret_fallback")

    has_credentials = bool(
        key_id and 
        key_secret and 
        key_id.startswith("rzp_test_") and 
        "xxxx" not in key_id
    )

    seed_db(reset=True)
    client = TestClient(app)
    db = SessionLocal()

    merchant = db.query(Merchant).first()
    m_id = merchant.id

    p_shoes = db.query(Product).filter(Product.name == "Pro Running Shoes").first()
    p_socks = db.query(Product).filter(Product.name == "Performance Socks").first()

    # Create Cart and Purchase Intent
    session_id = "sess_gate_demo"
    client.post("/api/v1/ai/shopping", json={"session_id": session_id, "merchant_id": m_id, "message": f"add product {p_shoes.id} to cart"})
    client.post("/api/v1/ai/shopping", json={"session_id": session_id, "merchant_id": m_id, "message": f"add product {p_socks.id} to cart"})

    res_pi = client.post("/api/v1/ai/purchase-intents", json={
        "session_id": session_id,
        "buyer_id": "buyer_gate_001",
        "merchant_id": m_id,
        "constraints": {"max_price": 4000.0, "currency": "INR", "quantity": 2}
    })
    pi = res_pi.json()
    pi_id = pi["id"]

    res_eval = client.post(f"/api/v1/purchase-intents/{pi_id}/evaluate?merchant_id={m_id}")
    auth_data = res_eval.json()["authorization"]
    auth_id = auth_data["id"]

    # ---------------------------------------------------------
    # PART 1: MOCK PAYMENT PROVIDER VERIFICATION
    # ---------------------------------------------------------
    print("--- [1] MockPaymentProvider Verification ---")
    mock_order_res = client.post(f"/api/v1/payments/create-order?merchant_id={m_id}", json={
        "purchase_intent_id": pi_id,
        "authorization_id": auth_id,
        "idempotency_key": "idemp_mock_gate"
    })
    assert mock_order_res.status_code == 200
    mock_tx_id = mock_order_res.json()["payment_transaction_id"]
    mock_order_id = mock_order_res.json()["razorpay_order_id"]
    assert mock_order_id.startswith("order_mock_")
    print(f"✓ Mock Order Created: {mock_order_id}")

    # Process Mock Webhook
    mock_provider = PaymentService.get_mock_provider()
    mock_wh_payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_mock_settled_123",
                    "order_id": mock_order_id,
                    "amount": 389800,
                    "currency": "INR",
                    "status": "captured"
                }
            }
        }
    }
    raw_mock = json.dumps(mock_wh_payload).encode("utf-8")
    sig_mock = mock_provider.generate_signature(raw_mock)
    res_mock_wh = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_mock,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": sig_mock,
            "X-Razorpay-Event-Id": "evt_mock_gate_001"
        }
    )
    assert res_mock_wh.status_code == 200
    mock_tx = db.query(PaymentTransaction).filter(PaymentTransaction.id == mock_tx_id).first()
    assert mock_tx.status == PaymentState.CAPTURED
    print(f"✓ Mock Webhook Processed & Captured: Status = {mock_tx.status}")
    print("MockPaymentProvider: PASS\n")

    # ---------------------------------------------------------
    # PART 2: REAL RAZORPAY TEST MODE EXECUTION
    # ---------------------------------------------------------
    print("--- [2] Real Razorpay Test Mode Verification ---")
    if not has_credentials:
        print("Razorpay Test Mode not executed — credentials unavailable")
        print("\nTo execute with live Razorpay Test API, provide:")
        print("  export RAZORPAY_KEY_ID=rzp_test_xxxxxxxxxxxxxx")
        print("  export RAZORPAY_KEY_SECRET=xxxxxxxxxxxxxxxxxxxxxx")
        print("  export RAZORPAY_WEBHOOK_SECRET=xxxxxxxxxxxxxxxxxxxxxx\n")
        return {
            "mock_pass": True,
            "real_executed": False,
            "reason": "credentials_unavailable"
        }

    print("RAZORPAY TEST MODE ACTIVE (Test mode credentials detected)")
    real_provider = RazorpayProvider(
        key_id=key_id,
        key_secret=key_secret,
        webhook_secret=webhook_secret
    )

    # Create fresh Purchase Intent & Authorization for Real Test
    session_id_real = "sess_gate_real"
    client.post("/api/v1/ai/shopping", json={"session_id": session_id_real, "merchant_id": m_id, "message": f"add product {p_shoes.id} to cart"})
    res_pi_real = client.post("/api/v1/ai/purchase-intents", json={
        "session_id": session_id_real,
        "buyer_id": "buyer_gate_real",
        "merchant_id": m_id,
        "constraints": {"max_price": 5000.0, "currency": "INR"}
    })
    pi_real_id = res_pi_real.json()["id"]
    res_eval_real = client.post(f"/api/v1/purchase-intents/{pi_real_id}/evaluate?merchant_id={m_id}")
    auth_real_id = res_eval_real.json()["authorization"]["id"]

    # Call Real Razorpay Orders API
    real_tx = PaymentService.create_payment_order(
        db=db,
        merchant_id=m_id,
        purchase_intent_id=pi_real_id,
        authorization_id=auth_real_id,
        idempotency_key="idemp_real_gate_001",
        provider_override=real_provider
    )
    real_order_id = real_tx.razorpay_order_id
    assert real_order_id.startswith("order_")
    assert not real_order_id.startswith("order_mock_")
    print(f"✓ Real Razorpay Order ID created: {real_order_id[:8]}...{real_order_id[-4:]}")

    # Fetch Real Order from Gateway
    fetched = real_provider.fetch_order(real_order_id)
    assert fetched.order_id == real_order_id
    print(f"✓ Real Gateway Order Verified via fetch_order: Amount = ₹{fetched.amount_minor / 100:.2f}")

    # Process Real Test Mode Webhook with HMAC
    real_pay_id = f"pay_test_{os.urandom(6).hex()}"
    real_wh_payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": real_pay_id,
                    "order_id": real_order_id,
                    "amount": fetched.amount_minor,
                    "currency": "INR",
                    "status": "captured"
                }
            }
        }
    }
    raw_real = json.dumps(real_wh_payload).encode("utf-8")
    import hmac, hashlib
    sig_real = hmac.new(webhook_secret.encode("utf-8"), raw_real, hashlib.sha256).hexdigest()
    event_id = f"evt_real_gate_{os.urandom(4).hex()}"

    res_real_wh = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_real,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": sig_real,
            "X-Razorpay-Event-Id": event_id
        }
    )
    assert res_real_wh.status_code == 200
    print("✓ Real Webhook HMAC-SHA256 Signature Verified")

    # Verify deduplication
    res_real_dup = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_real,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": sig_real,
            "X-Razorpay-Event-Id": event_id
        }
    )
    assert res_real_dup.status_code == 200
    print("✓ Webhook Deduplication Verified (Duplicate safely acknowledged)")

    db.refresh(real_tx)
    assert real_tx.status == PaymentState.CAPTURED
    assert real_tx.razorpay_payment_id == real_pay_id
    print(f"✓ Final Server-Side State Verified: CAPTURED (Payment ID: {real_pay_id[:8]}...)")

    return {
        "mock_pass": True,
        "real_executed": True,
        "real_order_id": f"{real_order_id[:8]}...{real_order_id[-4:]}",
        "real_payment_id": f"{real_pay_id[:8]}...{real_pay_id[-4:]}"
    }

if __name__ == "__main__":
    verify_razorpay_gate()
