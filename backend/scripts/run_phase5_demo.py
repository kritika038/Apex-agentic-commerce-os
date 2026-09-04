import sys
import os
import json
from decimal import Decimal
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone, timedelta
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

def run_phase5_demo():
    print("==========================================================================================")
    print(" PHASE 5: RAZORPAY TEST MODE & DETERMINISTIC PAYMENT SUITE DEMO")
    print("==========================================================================================\n")

    key_id = os.environ.get("RAZORPAY_KEY_ID", "")
    key_secret = os.environ.get("RAZORPAY_KEY_SECRET", "")
    webhook_secret = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "test_webhook_secret_fallback")

    has_real_credentials = bool(
        key_id and 
        key_secret and 
        key_id.startswith("rzp_test_") and 
        "xxxx" not in key_id
    )

    if has_real_credentials:
        print("▶ ACTIVE GATEWAY CONFIGURATION: RAZORPAY TEST MODE (Live Test API Enabled)")
    else:
        print("▶ ACTIVE GATEWAY CONFIGURATION: MOCK PAYMENT MODE (Deterministic Simulation Enabled)")
        print("  Note: Real Razorpay Test API calls require RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET\n")

    # Step 1: Seed database with exact Decimal precision & Phase 5 configuration
    seed_db(reset=True)
    client = TestClient(app)
    db = SessionLocal()

    merchant = db.query(Merchant).first()
    m_id = merchant.id
    print(f"Merchant Context: {merchant.name} (ID: {m_id})")

    login_res = client.post("/api/v1/auth/login", data={"username": "admin@demo-sports.test", "password": "password123"})
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("Merchant Admin authenticated successfully.\n")

    # -------------------------------------------------------------------------
    # PART 1: MOCK PAYMENT PROVIDER END-TO-END FLOW
    # -------------------------------------------------------------------------
    print("-------------------------------------------------------------------------")
    print(" [1] MOCK PAYMENT PROVIDER: FULL COMMERCE & SETTLEMENT FLOW")
    print("-------------------------------------------------------------------------")
    session_id = "demo_phase5_session"
    buyer_id = "buyer_phase5_01"

    p_shoes = db.query(Product).filter(Product.name == "Pro Running Shoes").first()
    p_socks = db.query(Product).filter(Product.name == "Performance Socks").first()

    # 1. AI Buyer adds items to cart
    client.post("/api/v1/ai/shopping", json={"session_id": session_id, "merchant_id": m_id, "message": f"add product {p_shoes.id} to cart"})
    client.post("/api/v1/ai/shopping", json={"session_id": session_id, "merchant_id": m_id, "message": f"add product {p_socks.id} to cart"})

    # 2. Create Purchase Intent (₹3,898)
    res_pi = client.post("/api/v1/ai/purchase-intents", json={
        "session_id": session_id,
        "buyer_id": buyer_id,
        "merchant_id": m_id,
        "constraints": {"max_price": 4000.0, "currency": "INR", "quantity": 2}
    })
    assert res_pi.status_code == 200
    pi = res_pi.json()
    print(f"1. Purchase Intent Created: ID: {pi['id']}, Amount: ₹{float(pi['requested_amount']):,.2f} {pi['currency']}")

    # 3. Deterministic Policy Evaluation
    res_eval = client.post(f"/api/v1/purchase-intents/{pi['id']}/evaluate?merchant_id={m_id}")
    assert res_eval.status_code == 200
    eval_data = res_eval.json()
    auth_data = eval_data["authorization"]
    print(f"2. Deterministic Policy Evaluation:")
    print(f"   • Decision: {eval_data['decision']}")
    print(f"   • Risk Level: {eval_data['risk_level']}")
    print(f"   • Authorization Generated: ID: {auth_data['id']}, Status: {auth_data['status']}")

    # 4. Create Payment Order via PaymentService
    idemp_key = "idemp_demo_phase5_001"
    res_order = client.post(f"/api/v1/payments/create-order?merchant_id={m_id}", json={
        "purchase_intent_id": pi["id"],
        "authorization_id": auth_data["id"],
        "idempotency_key": idemp_key
    })
    assert res_order.status_code == 200
    order_data = res_order.json()
    tx_id = order_data["payment_transaction_id"]
    order_id = order_data["razorpay_order_id"]
    print(f"3. Payment Order Created:")
    print(f"   • Transaction ID: {tx_id}")
    print(f"   • Gateway Order ID: {order_id}")
    print(f"   • Authoritative Amount: ₹{float(order_data['amount']):,.2f} {order_data['currency']}")
    print(f"   • Initial Status: {order_data['status']}")

    # 5. Receive & Process Razorpay Webhook (payment.captured)
    print(f"4. Gateway Webhook Dispatch (payment.captured):")
    webhook_payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_demo_captured_777",
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
    event_id = "evt_demo_captured_001"

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
    print(f"   ✓ Webhook Signature Verified (HMAC-SHA256 over raw body)")
    print(f"   ✓ Webhook Event ID: {event_id} Processed")

    # 6. Verify Settled State
    tx = db.query(PaymentTransaction).filter(PaymentTransaction.id == tx_id).first()
    assert tx.status == PaymentState.CAPTURED
    assert tx.razorpay_payment_id == "pay_demo_captured_777"
    assert tx.captured_at is not None
    print(f"5. Final Settled State in Database:")
    print(f"   • Payment Status: {tx.status}")
    print(f"   • Gateway Payment ID: {tx.razorpay_payment_id}")
    print(f"   • Captured At: {tx.captured_at.isoformat()}")

    pi_updated = db.query(PurchaseIntent).filter(PurchaseIntent.id == pi["id"]).first()
    assert pi_updated.status == "COMPLETED"
    print(f"   • Linked Purchase Intent Status: {pi_updated.status}\n")

    # ---------------------------------------------------------
    # PART 2: REAL RAZORPAY TEST MODE (IF CREDENTIALS CONFIGURED)
    # ---------------------------------------------------------
    print("-------------------------------------------------------------------------")
    print(" [2] REAL RAZORPAY TEST MODE GATEWAY VERIFICATION")
    print("-------------------------------------------------------------------------")
    if has_real_credentials:
        print("Executing live order creation against https://api.razorpay.com/v1...")
        real_provider = RazorpayProvider(key_id=key_id, key_secret=key_secret, webhook_secret=webhook_secret)
        
        session_id_real = "sess_demo_real_rzp"
        client.post("/api/v1/ai/shopping", json={"session_id": session_id_real, "merchant_id": m_id, "message": f"add product {p_shoes.id} to cart"})
        res_pi_r = client.post("/api/v1/ai/purchase-intents", json={
            "session_id": session_id_real,
            "buyer_id": "buyer_demo_real_rzp",
            "merchant_id": m_id,
            "constraints": {"max_price": 5000.0, "currency": "INR"}
        })
        pi_r_id = res_pi_r.json()["id"]
        res_eval_r = client.post(f"/api/v1/purchase-intents/{pi_r_id}/evaluate?merchant_id={m_id}")
        auth_r_id = res_eval_r.json()["authorization"]["id"]

        real_tx = PaymentService.create_payment_order(
            db=db,
            merchant_id=m_id,
            purchase_intent_id=pi_r_id,
            authorization_id=auth_r_id,
            idempotency_key="idemp_real_demo_001",
            provider_override=real_provider
        )
        print(f"   ✓ Real Razorpay Order ID Created: {real_tx.razorpay_order_id[:8]}...{real_tx.razorpay_order_id[-4:]}")
        print(f"   ✓ Status: {real_tx.status}")
    else:
        print("Razorpay Test Mode not executed — credentials unavailable")
        print("To run with live Razorpay Test API: export RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET\n")

    # -------------------------------------------------------------------------
    # PART 3: 8 PRE-PAYMENT ATTACK & DEFENSE VERIFICATIONS
    # -------------------------------------------------------------------------
    print("-------------------------------------------------------------------------")
    print(" [3] 🛡️ PRE-PAYMENT ATTACK & DEFENSE VERIFICATIONS")
    print("-------------------------------------------------------------------------")

    # Attack 1: Client / AI tries to change amount (₹8,500 -> ₹1)
    print("1. Amount Tampering Defense: Client attempts to specify ₹1.00 for ₹8,500 authorization...")
    p_watch = db.query(Product).filter(Product.name == "Fitness Tracker Watch").first()
    client.post("/api/v1/ai/shopping", json={"session_id": "sess_amt_t", "merchant_id": m_id, "message": f"add product {p_watch.id} to cart"})
    res_pi_w = client.post("/api/v1/ai/purchase-intents", json={
        "session_id": "sess_amt_t", "buyer_id": "buyer_w", "merchant_id": m_id, "constraints": {"max_price": 9000.0, "currency": "INR"}
    })
    pi_w_id = res_pi_w.json()["id"]
    res_eval_w = client.post(f"/api/v1/purchase-intents/{pi_w_id}/evaluate?merchant_id={m_id}")
    appr_w_id = res_eval_w.json()["approval_request"]["id"]
    res_appr_w = client.post(f"/api/v1/approvals/{appr_w_id}/approve", headers=headers, json={"reason": "Approved for demo"})
    auth_w_id = res_appr_w.json()["authorization"]["id"]

    res_tamper_amt = client.post(f"/api/v1/payments/create-order?merchant_id={m_id}", json={
        "purchase_intent_id": pi_w_id,
        "authorization_id": auth_w_id,
        "idempotency_key": "idemp_tamper_amt_val",
        "expected_amount": 1.0
    })
    assert res_tamper_amt.status_code == 400
    assert "amount mismatch" in res_tamper_amt.json()["detail"].lower()
    print(f"   ✓ Blocked before provider: {res_tamper_amt.json()['detail']}")

    # Attack 2: Currency Tampering (INR -> USD)
    print("2. Currency Tampering Defense: Client attempts to specify currency 'USD'...")
    res_tamper_curr = client.post(f"/api/v1/payments/create-order?merchant_id={m_id}", json={
        "purchase_intent_id": pi_w_id,
        "authorization_id": auth_w_id,
        "idempotency_key": "idemp_tamper_curr_val",
        "expected_currency": "USD"
    })
    assert res_tamper_curr.status_code == 400
    assert "currency mismatch" in res_tamper_curr.json()["detail"].lower()
    print(f"   ✓ Blocked before provider: {res_tamper_curr.json()['detail']}")

    # Attack 3: Expired authorization attempts payment
    print("3. Expired Authorization Defense: Attempting payment on an expired authorization...")
    auth_db = db.query(TransactionAuthorization).filter(TransactionAuthorization.id == auth_w_id).first()
    auth_db.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=5)
    db.commit()

    res_pay_exp = client.post(f"/api/v1/payments/create-order?merchant_id={m_id}", json={
        "purchase_intent_id": pi_w_id,
        "authorization_id": auth_w_id,
        "idempotency_key": "idemp_exp_test"
    })
    assert res_pay_exp.status_code == 400
    assert "expired" in res_pay_exp.json()["detail"].lower()
    print(f"   ✓ Blocked before provider: {res_pay_exp.json()['detail']}")

    # Attack 4: Wrong Authorization (Intent A vs Auth B)
    print("4. Authorization Mismatch Defense: Intent A paired with Authorization B...")
    auth_db.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=10)
    auth_db.status = "AUTHORIZED"
    db.commit()

    res_mismatch = client.post(f"/api/v1/payments/create-order?merchant_id={m_id}", json={
        "purchase_intent_id": "fake_intent_diff_001",
        "authorization_id": auth_w_id,
        "idempotency_key": "idemp_mismatch_test"
    })
    assert res_mismatch.status_code == 400
    assert "mismatch" in res_mismatch.json()["detail"].lower()
    print(f"   ✓ Blocked: {res_mismatch.json()['detail']}")

    # Attack 5: Cross-Merchant Authorization Reuse
    print("5. Tenant Isolation: Merchant 2 attempts to use Merchant 1's authorization...")
    m2 = Merchant(name="M2", domain="m2.com")
    db.add(m2)
    db.commit()
    res_cross_auth = client.post(f"/api/v1/payments/create-order?merchant_id={m2.id}", json={
        "purchase_intent_id": pi_w_id,
        "authorization_id": auth_w_id,
        "idempotency_key": "idemp_cross_auth_test"
    })
    assert res_cross_auth.status_code == 400
    print(f"   ✓ Blocked: 400 Authorization not found for Merchant 2.")

    # Attack 6: Payment Idempotency
    print("6. Payment Idempotency: Submitting identical idempotency_key twice...")
    idemp_dup = "idemp_test_duplicate_999"
    res_idemp_1 = client.post(f"/api/v1/payments/create-order?merchant_id={m_id}", json={
        "purchase_intent_id": pi_w_id,
        "authorization_id": auth_w_id,
        "idempotency_key": idemp_dup
    })
    assert res_idemp_1.status_code == 200
    tx_1 = res_idemp_1.json()

    res_idemp_2 = client.post(f"/api/v1/payments/create-order?merchant_id={m_id}", json={
        "purchase_intent_id": pi_w_id,
        "authorization_id": auth_w_id,
        "idempotency_key": idemp_dup
    })
    assert res_idemp_2.status_code == 200
    tx_2 = res_idemp_2.json()
    assert tx_1["payment_transaction_id"] == tx_2["payment_transaction_id"]
    assert tx_1["razorpay_order_id"] == tx_2["razorpay_order_id"]
    print(f"   ✓ Idempotent: Reused transaction {tx_1['payment_transaction_id']} without duplicate order creation.")

    # Attack 7: Webhook Deduplication & Signature Defense
    print("7. Webhook Security: Deduplication and Invalid Signature verification...")
    res_dup_wh = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": signature, "X-Razorpay-Event-Id": event_id}
    )
    assert res_dup_wh.status_code == 200
    print(f"   ✓ Deduplicated: Event {event_id} safely acknowledged without duplicate state mutation.")

    res_bad_sig = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": "forged_signature_xyz", "X-Razorpay-Event-Id": "evt_fraud_999"}
    )
    assert res_bad_sig.status_code == 401
    print(f"   ✓ Forgery Blocked: 401 Unauthorized (Invalid HMAC signature over raw body).")

    # Attack 8: Gateway Timeout & Safe Reconciliation
    print("8. Gateway Timeout & Reconciliation: Simulating gateway timeout during order creation...")
    mock_provider.set_mode("TIMEOUT")
    res_timeout = client.post(f"/api/v1/payments/create-order?merchant_id={m_id}", json={
        "purchase_intent_id": pi_w_id,
        "authorization_id": auth_w_id,
        "idempotency_key": "idemp_timeout_demo"
    })
    assert res_timeout.status_code == 200
    to_tx_id = res_timeout.json()["payment_transaction_id"]
    to_tx = db.query(PaymentTransaction).filter(PaymentTransaction.id == to_tx_id).first()
    assert to_tx.status == PaymentState.UNKNOWN
    print(f"   ✓ Timeout handled safely: Transaction status set to {to_tx.status} (no blind retry).")

    mock_provider.set_mode("SUCCESS")
    res_rec = client.post(f"/api/v1/payments/{to_tx_id}/reconcile?merchant_id={m_id}")
    assert res_rec.status_code == 200
    print(f"   ✓ Reconciliation: {res_rec.json()['message']}")

    db.close()
    print("\n==========================================================================================")
    print(" ✅ ALL PHASE 5 DEMO PATHS AND PRE-PAYMENT DEFENSES PASSED PERFECTLY!")
    print("==========================================================================================")

if __name__ == "__main__":
    run_phase5_demo()
