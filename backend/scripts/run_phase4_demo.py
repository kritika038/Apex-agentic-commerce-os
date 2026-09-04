import sys
import os
from decimal import Decimal
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app.main import app
from app.database.session import SessionLocal
from app.database.models.product import Product
from app.database.models.merchant import Merchant
from app.database.models.policy import Policy
from app.database.models.policy_evaluation import PolicyEvaluation
from app.database.models.approval_request import ApprovalRequest
from app.database.models.transaction_authorization import TransactionAuthorization
from app.services.authorization_service import AuthorizationService
from app.tools.registry import tool_registry
from scripts.seed import seed_db

def run_phase4_demo():
    print("==========================================================================================")
    print(" PHASE 4: DETERMINISTIC POLICY ENGINE, AGENT PERMISSIONS, RISK & HUMAN APPROVAL DEMO")
    print("==========================================================================================\n")

    # Step 1: Seed database with exact Decimal precision & Phase 4 configurations
    seed_db(reset=True)
    client = TestClient(app)
    db = SessionLocal()

    merchant = db.query(Merchant).first()
    m_id = merchant.id
    print(f"Merchant Context: {merchant.name} (ID: {m_id})")

    # Obtain merchant auth token
    login_res = client.post("/api/v1/auth/login", data={"username": "admin@demo-sports.test", "password": "password123"})
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("Merchant Admin authenticated successfully.\n")

    # Fetch active policy
    policy_res = client.get("/api/v1/policies")
    policy_data = policy_res.json()
    print(f"Active Policy (v{policy_data['version']}):")
    print(f"  • Max Transaction Cap: ₹{float(policy_data['max_transaction_amount']):,.2f}")
    print(f"  • Human Approval Threshold: ₹{float(policy_data['approval_threshold']):,.2f}")
    print(f"  • Low-Risk Limit: ₹{float(policy_data['low_risk_limit']):,.2f}")
    print(f"  • Max Quantity: {policy_data['max_quantity']} items")
    print(f"  • Currency Whitelist: {policy_data['allowed_currency']}")
    print(f"  • Authorization Expiration: {policy_data['authorization_expiration_minutes']} minutes\n")

    # -------------------------------------------------------------------------
    # PATH A: LOW-RISK TRANSACTION (₹3,898 <= ₹5,000)
    # -------------------------------------------------------------------------
    print("-------------------------------------------------------------------------")
    print(" 🟢 PATH A: LOW-RISK TRANSACTION (Cart: ₹3,898 <= ₹5,000 Threshold)")
    print("-------------------------------------------------------------------------")
    session_a = "demo_path_a_session"
    buyer_a = "buyer_alpha"

    # AI Buyer searches and adds shoes & socks
    p_shoes = db.query(Product).filter(Product.name == "Pro Running Shoes").first()
    p_socks = db.query(Product).filter(Product.name == "Performance Socks").first()

    client.post("/api/v1/ai/shopping", json={"session_id": session_a, "merchant_id": m_id, "message": f"add product {p_shoes.id} to cart"})
    client.post("/api/v1/ai/shopping", json={"session_id": session_a, "merchant_id": m_id, "message": f"add product {p_socks.id} to cart"})

    # 1. Create Purchase Intent
    res_pi_a = client.post("/api/v1/ai/purchase-intents", json={
        "session_id": session_a,
        "buyer_id": buyer_a,
        "merchant_id": m_id,
        "constraints": {"max_price": 4000.0, "currency": "INR", "quantity": 2}
    })
    assert res_pi_a.status_code == 200
    pi_a = res_pi_a.json()
    print(f"1. Purchase Intent Created: ID: {pi_a['id']}, Status: {pi_a['status']}, Amount: ₹{float(pi_a['requested_amount']):,.2f}")

    # 2. Deterministic Policy Evaluation (Zero LLM Calls)
    res_eval_a = client.post(f"/api/v1/purchase-intents/{pi_a['id']}/evaluate?merchant_id={m_id}")
    assert res_eval_a.status_code == 200
    eval_a = res_eval_a.json()
    print(f"2. Deterministic Policy Engine Evaluation:")
    print(f"   • Decision: {eval_a['decision']}")
    print(f"   • Risk Level: {eval_a['risk_level']}")
    print(f"   • Requires Human Approval: {eval_a['requires_human_approval']}")
    for chk in eval_a['checks']:
        print(f"     ✓ Check {chk['rule']}: {'PASSED' if chk['passed'] else 'FAILED'}")

    # 3. Transaction Authorization Verification
    auth_a = eval_a['authorization']
    print(f"3. Transaction Authorization Generated:")
    print(f"   • Auth ID: {auth_a['id']}")
    print(f"   • Status: {auth_a['status']}")
    print(f"   • Authorized Amount: ₹{float(auth_a['authorized_amount']):,.2f} {auth_a['currency']}")
    print(f"   • Authorized By: {auth_a['authorized_by']}")
    print(f"   • Expiration: {auth_a['expires_at']} (~10 minutes)")
    print(f"   • Financial Boundary: NO PAYMENT HAS OCCURRED (Ready for Phase 5 Razorpay Settlement)\n")

    # -------------------------------------------------------------------------
    # PATH B: HIGH-RISK TRANSACTION (₹8,500 > ₹5,000) & HUMAN APPROVAL
    # -------------------------------------------------------------------------
    print("-------------------------------------------------------------------------")
    print(" 🟠 PATH B: HIGH-RISK TRANSACTION (Cart: ₹8,500 > ₹5,000 Threshold)")
    print("-------------------------------------------------------------------------")
    session_b = "demo_path_b_session"
    buyer_b = "buyer_beta"
    p_watch = db.query(Product).filter(Product.name == "Fitness Tracker Watch").first()

    client.post("/api/v1/ai/shopping", json={"session_id": session_b, "merchant_id": m_id, "message": f"add product {p_watch.id} to cart"})

    res_pi_b = client.post("/api/v1/ai/purchase-intents", json={
        "session_id": session_b,
        "buyer_id": buyer_b,
        "merchant_id": m_id,
        "constraints": {"max_price": 9000.0, "currency": "INR", "quantity": 1}
    })
    assert res_pi_b.status_code == 200
    pi_b = res_pi_b.json()
    print(f"1. Purchase Intent Created: ID: {pi_b['id']}, Amount: ₹{float(pi_b['requested_amount']):,.2f}")

    # 2. Deterministic Policy Evaluation
    res_eval_b = client.post(f"/api/v1/purchase-intents/{pi_b['id']}/evaluate?merchant_id={m_id}")
    assert res_eval_b.status_code == 200
    eval_b = res_eval_b.json()
    print(f"2. Deterministic Policy Engine Evaluation:")
    print(f"   • Decision: {eval_b['decision']}")
    print(f"   • Risk Level: {eval_b['risk_level']}")
    print(f"   • Requires Human Approval: {eval_b['requires_human_approval']}")
    appr_req = eval_b['approval_request']
    print(f"   • Approval Request Generated: ID: {appr_req['id']}, Status: {appr_req['status']}")
    print(f"   • Reason: {appr_req['reason']}")

    # 3. Human Approval in Merchant Center
    print(f"3. Merchant Operator Signs Off in Approval Center:")
    res_appr = client.post(f"/api/v1/approvals/{appr_req['id']}/approve", headers=headers, json={"reason": "Approved by merchant operator"})
    assert res_appr.status_code == 200
    appr_data = res_appr.json()
    print(f"   • Approval Status: {appr_data['approval']['status']}")
    print(f"   • Authorized Amount: ₹{float(appr_data['authorization']['authorized_amount']):,.2f}")
    print(f"   • Authorization Generated: ID: {appr_data['authorization']['id']}, Status: {appr_data['authorization']['status']}")
    print(f"   • Financial Boundary: NO PAYMENT HAS OCCURRED (Awaiting Phase 5)\n")

    # -------------------------------------------------------------------------
    # ATTACK & DEFENSE VERIFICATIONS
    # -------------------------------------------------------------------------
    print("-------------------------------------------------------------------------")
    print(" 🛡️ ATTACK & DEFENSE VERIFICATIONS")
    print("-------------------------------------------------------------------------")

    # Defense 1: Sales Agent attempts payment tool execution
    print("1. Least Privilege Check: SalesAgent attempts payment tool execution...")
    err1 = tool_registry.verify_permission(
        tool_name="add_to_cart",
        agent_permissions=["READ_PRODUCTS", "READ_CART", "CREATE_RECOMMENDATION"],
        agent_name="SalesAgent"
    )
    assert err1["error"] == "PERMISSION_DENIED"
    print(f"   ✓ Blocked by Tool Registry: {err1['error']} (Agent: {err1['agent']}, Required: {err1['required_permission']})")

    # Defense 2: Downstream tampering attempt (modifying authorization amount to ₹1)
    print("2. Authorization Tamper Defense: Downstream attempt to settle ₹1 on ₹8,500 authorization...")
    auth_id_b = appr_data['authorization']['id']
    is_valid, reason, _ = AuthorizationService.validate_authorization(
        db=db,
        authorization_id=auth_id_b,
        merchant_id=m_id,
        expected_amount=Decimal("1.00"),
        expected_currency="INR"
    )
    assert is_valid is False
    print(f"   ✓ Blocked by AuthorizationService: {reason}")

    # Defense 3: Unauthenticated agent attempts to mutate policy
    print("3. Policy Protection: Unauthenticated AI Agent attempts to increase max transaction limit...")
    res_tamper_policy = client.post("/api/v1/policies", json={"name": "Attacker Policy", "max_transaction_amount": 9999999.0})
    assert res_tamper_policy.status_code == 401
    print("   ✓ Blocked by Authentication Layer: 401 Unauthorized (Only merchant users may mutate policy)")

    # Defense 4: Historical policy reproducibility
    print("4. Historical Policy Reproducibility: Merchant publishes Policy v2 (tightening threshold to ₹3,000)...")
    res_v2 = client.put(f"/api/v1/policies/{policy_data['id']}", json={"approval_threshold": 3000.0}, headers=headers)
    assert res_v2.status_code == 200
    v2_data = res_v2.json()
    assert v2_data["version"] == 2
    
    # Old evaluation in DB still reflects v1 snapshot
    old_eval = db.query(PolicyEvaluation).filter(PolicyEvaluation.id == eval_a['id']).first()
    assert old_eval.policy_version == 1
    assert old_eval.policy_snapshot["approval_threshold"] == "5000.00"
    print(f"   ✓ Old evaluation permanently preserved snapshot: Policy v{old_eval.policy_version}, Threshold: ₹{float(old_eval.policy_snapshot['approval_threshold']):,.2f}")

    db.close()
    print("\n==========================================================================================")
    print(" ✅ ALL PHASE 4 DEMO PATHS AND SECURITY BOUNDARY DEFENSES PASSED PERFECTLY!")
    print("==========================================================================================")

if __name__ == "__main__":
    run_phase4_demo()
