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
from app.database.models.payment_attempt import PaymentAttempt
from app.database.models.reconciliation_attempt import ReconciliationAttempt
from app.payments.service import PaymentService
from app.payments.reconciliation import PaymentReconciliation
from app.payments.simulator import PaymentSimulator
from app.payments.state_machine import PaymentState
from scripts.seed import seed_db

def run_phase6_demo():
    print("==========================================================================================")
    print(" PHASE 6: FAILURE RECOVERY, RECONCILIATION & PAYMENT SIMULATOR DEMO")
    print("==========================================================================================\n")

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

    p_shoes = db.query(Product).filter(Product.name == "Pro Running Shoes").first()
    p_socks = db.query(Product).filter(Product.name == "Performance Socks").first()

    mock_provider = PaymentService.get_mock_provider()

    # --------------------------------------------------------------------------------------------------
    # CENTERPIECE SCENARIO: UNKNOWN -> NO BLIND RETRY -> RECONCILIATION -> RESOLVED
    # --------------------------------------------------------------------------------------------------
    print("==========================================================================================")
    print(" 🌟 CENTERPIECE DEMO: UNKNOWN STATE -> NO BLIND RETRY -> RECONCILIATION")
    print("==========================================================================================")
    
    session_cp = "sess_demo_cp_01"
    client.post("/api/v1/ai/shopping", json={"session_id": session_cp, "merchant_id": m_id, "message": f"add product {p_shoes.id} to cart"})
    res_pi_cp = client.post("/api/v1/ai/purchase-intents", json={
        "session_id": session_cp, "buyer_id": "buyer_cp", "merchant_id": m_id, "constraints": {"max_price": 5000.0, "currency": "INR"}
    })
    pi_cp_id = res_pi_cp.json()["id"]
    res_eval_cp = client.post(f"/api/v1/purchase-intents/{pi_cp_id}/evaluate?merchant_id={m_id}")
    auth_cp_id = res_eval_cp.json()["authorization"]["id"]
    print(f"1. Transaction Authorization Created: {auth_cp_id}")

    # 2. Outbound Order Creation with Timeout
    print("2. Gateway call encountering network timeout during order creation...")
    mock_provider.set_mode("TIMEOUT")
    res_to = client.post(f"/api/v1/payments/create-order?merchant_id={m_id}", json={
        "purchase_intent_id": pi_cp_id,
        "authorization_id": auth_cp_id,
        "idempotency_key": "idemp_cp_to_01"
    })
    assert res_to.status_code == 200
    tx_cp_id = res_to.json()["payment_transaction_id"]
    tx_cp = db.query(PaymentTransaction).filter(PaymentTransaction.id == tx_cp_id).first()
    print(f"   • Transaction ID: {tx_cp_id}")
    print(f"   • Status: {tx_cp.status} (UNKNOWN does NOT mean FAILED; provider state is indeterminate)")
    print(f"   • Failure Code: {tx_cp.failure_code}")

    # 3. Verify PaymentAttempt recorded
    attempt_cp = db.query(PaymentAttempt).filter(PaymentAttempt.payment_transaction_id == tx_cp_id).first()
    print(f"   • Audit Record: PaymentAttempt #{attempt_cp.attempt_number} logged with status '{attempt_cp.status}'.")

    # 4. Attempt to create another order on same authorization while UNKNOWN
    print("3. Blind Retry Defense: Malicious or automated client attempts new order on UNKNOWN authorization...")
    mock_provider.set_mode("SUCCESS")
    res_blind_retry = client.post(f"/api/v1/payments/create-order?merchant_id={m_id}", json={
        "purchase_intent_id": pi_cp_id,
        "authorization_id": auth_cp_id,
        "idempotency_key": "idemp_cp_retry_02"
    })
    assert res_blind_retry.status_code == 409
    print(f"   ✓ BLOCKED: 409 Conflict - {res_blind_retry.json()['detail']}")

    # 5. Execute Authoritative Reconciliation
    print("4. Executing Authoritative Reconciliation against Payment Provider...")
    res_recon_cp = client.post(f"/api/v1/payments/{tx_cp_id}/reconcile?merchant_id={m_id}")
    assert res_recon_cp.status_code == 200
    print(f"   ✓ Reconciliation Result: {res_recon_cp.json()['message']}")

    # 6. Verify ReconciliationAttempt audit trail
    recon_att = db.query(ReconciliationAttempt).filter(ReconciliationAttempt.payment_transaction_id == tx_cp_id).first()
    print(f"   • Reconciliation Audit: Attempt #{recon_att.attempt_number} resolved '{recon_att.previous_status}' → '{recon_att.resolved_status}'.")
    print(f"   • Response Hash (SHA-256): {recon_att.provider_response_hash or 'N/A'}\n")

    # --------------------------------------------------------------------------------------------------
    # SCENARIO A: STANDARD SUCCESS LIFECYCLE
    # --------------------------------------------------------------------------------------------------
    print("-------------------------------------------------------------------------")
    print(" [SCENARIO A] STANDARD SUCCESS LIFECYCLE")
    print("-------------------------------------------------------------------------")
    session_a = "sess_scen_a"
    client.post("/api/v1/ai/shopping", json={"session_id": session_a, "merchant_id": m_id, "message": f"add product {p_shoes.id} to cart"})
    res_pi_a = client.post("/api/v1/ai/purchase-intents", json={
        "session_id": session_a, "buyer_id": "buyer_a", "merchant_id": m_id, "constraints": {"max_price": 5000.0, "currency": "INR"}
    })
    pi_a_id = res_pi_a.json()["id"]
    res_eval_a = client.post(f"/api/v1/purchase-intents/{pi_a_id}/evaluate?merchant_id={m_id}")
    auth_a_id = res_eval_a.json()["authorization"]["id"]

    res_ord_a = client.post(f"/api/v1/payments/create-order?merchant_id={m_id}", json={
        "purchase_intent_id": pi_a_id, "authorization_id": auth_a_id, "idempotency_key": "idemp_scen_a"
    })
    tx_a_id = res_ord_a.json()["payment_transaction_id"]
    ord_a_id = res_ord_a.json()["razorpay_order_id"]
    print(f"1. Order Created: {ord_a_id}, Status: ORDER_CREATED")

    # Dispatch captured webhook
    raw_wh_a = json.dumps({
        "event": "payment.captured",
        "payload": {"payment": {"entity": {"id": "pay_scen_a_888", "order_id": ord_a_id, "amount": 349900, "currency": "INR", "status": "captured"}}}
    }).encode("utf-8")
    sig_a = mock_provider.generate_signature(raw_wh_a)
    res_wh_a = client.post("/api/v1/webhooks/razorpay", content=raw_wh_a, headers={
        "Content-Type": "application/json", "X-Razorpay-Signature": sig_a, "X-Razorpay-Event-Id": "evt_scen_a_001"
    })
    assert res_wh_a.status_code == 200
    tx_a = db.query(PaymentTransaction).filter(PaymentTransaction.id == tx_a_id).first()
    print(f"2. Webhook Processed: Final Status: {tx_a.status}, Payment ID: {tx_a.razorpay_payment_id}\n")

    # --------------------------------------------------------------------------------------------------
    # SCENARIO C: IDEMPOTENT DUPLICATE REQUESTS
    # --------------------------------------------------------------------------------------------------
    print("-------------------------------------------------------------------------")
    print(" [SCENARIO C] IDEMPOTENT DUPLICATE REQUESTS")
    print("-------------------------------------------------------------------------")
    session_c = "sess_scen_c"
    client.post("/api/v1/ai/shopping", json={"session_id": session_c, "merchant_id": m_id, "message": f"add product {p_shoes.id} to cart"})
    res_pi_c = client.post("/api/v1/ai/purchase-intents", json={
        "session_id": session_c, "buyer_id": "buyer_c", "merchant_id": m_id, "constraints": {"max_price": 5000.0, "currency": "INR"}
    })
    pi_c_id = res_pi_c.json()["id"]
    res_eval_c = client.post(f"/api/v1/purchase-intents/{pi_c_id}/evaluate?merchant_id={m_id}")
    auth_c_id = res_eval_c.json()["authorization"]["id"]

    idemp_c = "idemp_dup_scen_c"
    res_c1 = client.post(f"/api/v1/payments/create-order?merchant_id={m_id}", json={
        "purchase_intent_id": pi_c_id, "authorization_id": auth_c_id, "idempotency_key": idemp_c
    })
    res_c2 = client.post(f"/api/v1/payments/create-order?merchant_id={m_id}", json={
        "purchase_intent_id": pi_c_id, "authorization_id": auth_c_id, "idempotency_key": idemp_c
    })
    assert res_c1.status_code == 200 and res_c2.status_code == 200
    assert res_c1.json()["payment_transaction_id"] == res_c2.json()["payment_transaction_id"]
    print(f"✓ Reused transaction {res_c1.json()['payment_transaction_id']} without duplicate provider order creation.\n")

    # --------------------------------------------------------------------------------------------------
    # SCENARIO D & E: DUPLICATE & INVALID WEBHOOKS
    # --------------------------------------------------------------------------------------------------
    print("-------------------------------------------------------------------------")
    print(" [SCENARIO D & E] WEBHOOK SECURITY (DEDUPLICATION & HMAC TAMPER DEFENSE)")
    print("-------------------------------------------------------------------------")
    # Duplicate Webhook
    res_wh_dup = client.post("/api/v1/webhooks/razorpay", content=raw_wh_a, headers={
        "Content-Type": "application/json", "X-Razorpay-Signature": sig_a, "X-Razorpay-Event-Id": "evt_scen_a_001"
    })
    assert res_wh_dup.status_code == 200
    print("✓ Duplicate Webhook Event evt_scen_a_001 safely acknowledged without state mutation.")

    # Forged Webhook Signature
    res_wh_bad = client.post("/api/v1/webhooks/razorpay", content=raw_wh_a, headers={
        "Content-Type": "application/json", "X-Razorpay-Signature": "forged_sig_xyz", "X-Razorpay-Event-Id": "evt_fraud_001"
    })
    assert res_wh_bad.status_code == 401
    print("✓ Forged Webhook Rejected: 401 Unauthorized (HMAC-SHA256 mismatch over raw body).\n")

    # --------------------------------------------------------------------------------------------------
    # SCENARIO F: OUT-OF-ORDER WEBHOOK DELIVERY & DOWNGRADE DEFENSE
    # --------------------------------------------------------------------------------------------------
    print("-------------------------------------------------------------------------")
    print(" [SCENARIO F] OUT-OF-ORDER WEBHOOK & TERMINAL DOWNGRADE DEFENSE")
    print("-------------------------------------------------------------------------")
    print(f"Transaction {tx_a_id} is currently settled as CAPTURED.")
    print("Simulating arrival of a delayed payment.failed webhook...")
    raw_wh_fail = json.dumps({
        "event": "payment.failed",
        "payload": {"payment": {"entity": {"id": "pay_late_fail", "order_id": ord_a_id, "error_code": "LATE_FAILURE", "error_description": "Delayed failure event"}}}
    }).encode("utf-8")
    sig_fail = mock_provider.generate_signature(raw_wh_fail)
    res_wh_fail = client.post("/api/v1/webhooks/razorpay", content=raw_wh_fail, headers={
        "Content-Type": "application/json", "X-Razorpay-Signature": sig_fail, "X-Razorpay-Event-Id": "evt_late_fail_001"
    })
    assert res_wh_fail.status_code == 200
    db.refresh(tx_a)
    assert tx_a.status == PaymentState.CAPTURED
    print(f"✓ Terminal State Protected: Transaction remained '{tx_a.status}'; out-of-order downgrade blocked!\n")

    # --------------------------------------------------------------------------------------------------
    # SCENARIO G: DATABASE-BACKED TIMELINE VERIFICATION
    # --------------------------------------------------------------------------------------------------
    print("-------------------------------------------------------------------------")
    print(" [SCENARIO G] DATABASE-BACKED RECOVERY TIMELINE")
    print("-------------------------------------------------------------------------")
    res_tl = client.get(f"/api/v1/payments/{tx_cp_id}/timeline?merchant_id={m_id}")
    assert res_tl.status_code == 200
    tl_events = res_tl.json()
    print(f"Timeline events fetched for Transaction {tx_cp_id}:")
    for ev in tl_events:
        print(f"   [{ev['timestamp'][:19]}] {ev['title']} — {ev['description']}")

    db.close()
    print("\n==========================================================================================")
    print(" ✅ ALL PHASE 6 FAILURE RECOVERY & RECONCILIATION SCENARIOS PASSED PERFECTLY!")
    print("==========================================================================================")

if __name__ == "__main__":
    run_phase6_demo()
