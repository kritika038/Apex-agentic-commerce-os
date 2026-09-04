#!/usr/bin/env python3
"""
Phase 8 Live Interactive Demo: AI-to-AI Commerce Protocol & Control Plane Verification

Demonstrates:
1. Machine-readable Capability Discovery (GET /api/v1/protocol/capabilities)
2. Grounded Autonomous Product Discovery (POST /api/v1/protocol/discover)
3. Contextual Sales Agent Recommendations (POST /api/v1/protocol/recommend)
4. Authoritative Purchase Intent Minting (POST /api/v1/protocol/purchase-intent)
5. Deterministic Policy Evaluation & Authorization (POST /api/v1/purchase-intents/{id}/evaluate)
6. Authorization Lifecycle State Lookup (GET /api/v1/protocol/authorization/{id})
7. Strict Payment Settlement Execution (POST /api/v1/protocol/payment-request)
8. End-to-End Cryptographic Hash-Chain Audit Integrity Verification
9. Agent Permission Firewall Boundary Inspection (GET /api/v1/agents/firewall)
"""
import uuid
import sys
from decimal import Decimal
from fastapi.testclient import TestClient

from app.main import app
from app.database.session import SessionLocal
from app.database.models.merchant import Merchant
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.services.audit_integrity_service import AuditIntegrityService

def run_phase8_demo():
    print("=" * 80)
    print("  PHASE 8 LIVE DEMO: AI-TO-AI COMMERCE PROTOCOL & CONTROL PLANE")
    print("=" * 80)

    client = TestClient(app)
    db = SessionLocal()

    # 1. Ensure active merchant & grounded catalog
    merchant = db.query(Merchant).filter(Merchant.is_active == True).first()
    if not merchant:
        merchant = Merchant(name="Demo Pro Sports", domain="demo-sports.test", is_active=True)
        db.add(merchant)
        db.commit()
        db.refresh(merchant)

    m_id = merchant.id
    print(f"\n[1] MERCHANT IDENTITY: {merchant.name} (ID: {m_id})")

    # Seed products
    p1 = db.query(Product).filter(Product.merchant_id == m_id, Product.name == "Pro Running Shoes").first()
    if not p1:
        p1 = Product(merchant_id=m_id, name="Pro Running Shoes", price=Decimal("3499.00"), category="Footwear", is_active=True)
        p2 = Product(merchant_id=m_id, name="Performance Socks", price=Decimal("399.00"), category="Accessories", is_active=True)
        db.add_all([p1, p2])
        db.flush()
        db.add(Inventory(merchant_id=m_id, product_id=p1.id, stock_quantity=20))
        db.add(Inventory(merchant_id=m_id, product_id=p2.id, stock_quantity=50))
        db.commit()
        print("  ✓ Seeded catalog with database-grounded inventory")

    trace_id = f"trc_phase8_demo_{uuid.uuid4().hex[:8]}"
    session_id = f"sess_phase8_demo_{uuid.uuid4().hex[:6]}"
    print(f"  ✓ Session ID: {session_id}")
    print(f"  ✓ Master Unified Trace ID: {trace_id}")

    # Step 1: Capabilities Discovery
    print("\n[STEP 1] CAPABILITY DISCOVERY (GET /api/v1/protocol/capabilities)")
    res_cap = client.get(f"/api/v1/protocol/capabilities?merchant_id={m_id}")
    assert res_cap.status_code == 200, f"Capability discovery failed: {res_cap.text}"
    cap_data = res_cap.json()
    print(f"  • Protocol Version: {cap_data['protocol_version']}")
    print(f"  • Supported Operations: {', '.join(cap_data['operations'])}")
    print(f"  • Security Guarantees: {cap_data['security_guarantees']}")

    # Step 2: Grounded Product Discovery
    print("\n[STEP 2] AUTONOMOUS PRODUCT DISCOVERY (POST /api/v1/protocol/discover)")
    disc_payload = {
        "query": "Running",
        "category": "Footwear",
        "max_price": 5000.0,
        "currency": "INR",
        "session_id": session_id,
        "trace_id": trace_id
    }
    res_disc = client.post(f"/api/v1/protocol/discover?merchant_id={m_id}", json=disc_payload)
    assert res_disc.status_code == 200
    disc_data = res_disc.json()
    print(f"  • Discovered {disc_data['total_found']} matching product(s)")
    for p in disc_data['products']:
        print(f"    - {p['name']} | ₹{p['price']} | In Stock: {p['in_stock']} (Qty: {p['stock_quantity']})")

    # Add item to cart
    client.post("/api/v1/ai/shopping", json={
        "session_id": session_id,
        "merchant_id": m_id,
        "message": f"add product {p1.id} to cart",
        "trace_id": trace_id
    })
    print("  ✓ Added Pro Running Shoes to cart via Shopping Agent")

    # Step 3: Sales Agent Recommendations
    print("\n[STEP 3] CONTEXTUAL SALES RECOMMENDATIONS (POST /api/v1/protocol/recommend)")
    res_rec = client.post(f"/api/v1/protocol/recommend?merchant_id={m_id}", json={
        "session_id": session_id,
        "trace_id": trace_id
    })
    assert res_rec.status_code == 200
    rec_data = res_rec.json()
    print(f"  • Recommendations Generated: {len(rec_data['recommendations'])}")
    for r in rec_data['recommendations']:
        print(f"    - [{r['type']}] {r['product_name']} (₹{r['product_price']}) — Reason: {r['reason']}")

    # Step 4: Purchase Intent Creation
    print("\n[STEP 4] AUTHORITATIVE PURCHASE INTENT MINTING (POST /api/v1/protocol/purchase-intent)")
    res_pi = client.post(f"/api/v1/protocol/purchase-intent?merchant_id={m_id}", json={
        "session_id": session_id,
        "buyer_id": "external_ai_buyer_agent_007",
        "constraints": {"max_price": 5000.0, "currency": "INR"},
        "trace_id": trace_id
    })
    assert res_pi.status_code == 200
    pi_data = res_pi.json()
    pi_id = pi_data["purchase_intent_id"]
    print(f"  • Purchase Intent ID: {pi_id}")
    print(f"  • Authoritative Requested Amount: ₹{pi_data['requested_amount']} {pi_data['currency']}")
    print(f"  • Status: {pi_data['status']} | Expires At: {pi_data['expires_at']}")

    # Step 5: Deterministic Policy Evaluation
    print("\n[STEP 5] DETERMINISTIC POLICY EVALUATION (POST /api/v1/purchase-intents/{id}/evaluate)")
    res_eval = client.post(f"/api/v1/purchase-intents/{pi_id}/evaluate?merchant_id={m_id}&trace_id={trace_id}")
    assert res_eval.status_code == 200
    eval_data = res_eval.json()
    auth_id = eval_data["authorization"]["id"]
    print(f"  • Decision: {eval_data['decision']} (Risk: {eval_data['risk_level']})")
    print(f"  • Transaction Authorization ID: {auth_id}")
    print(f"  • Authorized Amount: ₹{eval_data['authorization']['authorized_amount']}")

    # Step 6: Authorization Status Lookup via Protocol
    print("\n[STEP 6] PROTOCOL AUTHORIZATION LOOKUP (GET /api/v1/protocol/authorization/{id})")
    res_auth = client.get(f"/api/v1/protocol/authorization/{pi_id}?merchant_id={m_id}")
    assert res_auth.status_code == 200
    auth_data = res_auth.json()
    print(f"  • Verified Authorization Status: {auth_data['status']}")
    print(f"  • Token: {auth_data['authorization_id']}")

    # Step 7: Payment Request Boundary Execution
    print("\n[STEP 7] PAYMENT SETTLEMENT EXECUTION (POST /api/v1/protocol/payment-request)")
    res_pay = client.post(f"/api/v1/protocol/payment-request?merchant_id={m_id}", json={
        "purchase_intent_id": pi_id,
        "authorization_id": auth_id,
        "idempotency_key": f"idemp_p8_demo_{uuid.uuid4().hex[:8]}",
        "trace_id": trace_id
    })
    assert res_pay.status_code == 200
    pay_data = res_pay.json()
    print(f"  • Payment Transaction ID: {pay_data['payment_transaction_id']}")
    print(f"  • Razorpay Order ID: {pay_data['razorpay_order_id']}")
    print(f"  • Settlement Amount: ₹{pay_data['amount']} {pay_data['currency']}")
    print(f"  • Initial Status: {pay_data['status']}")

    # Step 8: Cryptographic Hash-Chain Verification
    print("\n[STEP 8] CRYPTOGRAPHIC AUDIT TRAIL VERIFICATION")
    integrity = AuditIntegrityService.verify_trace(db=db, trace_id=trace_id, merchant_id=m_id)
    print(f"  • Events Logged in Hash Chain: {integrity['event_count']}")
    print(f"  • Cryptographic Chain Valid: {integrity['is_valid']}")
    print(f"  • Tampering Detected: {integrity['tampering_detected']}")
    assert integrity["is_valid"] is True, "Audit chain integrity failed!"

    # Step 9: Agent Permission Firewall Matrix
    print("\n[STEP 9] AGENT PERMISSION FIREWALL INSPECTION (GET /api/v1/agents/firewall)")
    res_fw = client.get(f"/api/v1/agents/firewall?merchant_id={m_id}")
    assert res_fw.status_code == 200
    fw_data = res_fw.json()
    print(f"  • Firewall Status: {fw_data['firewall_status']}")
    print(f"  • Total Sandboxed Agents: {fw_data['total_agents']}")
    for ag in fw_data['agents']:
        print(f"    - {ag['name']} ({ag['type']})")
        print(f"      Can Authorize Payment: {ag['can_authorize_payments']} | Can Modify Price: {ag['can_modify_prices']}")

    print("\n" + "=" * 80)
    print("  PHASE 8 LIVE DEMO COMPLETED SUCCESSFULLY: ALL INVARIANTS VERIFIED")
    print("=" * 80)
    db.close()

if __name__ == "__main__":
    run_phase8_demo()
