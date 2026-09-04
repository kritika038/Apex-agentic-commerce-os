import pytest
from decimal import Decimal
from fastapi.testclient import TestClient

from app.main import app
from app.database.models.merchant import Merchant
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.cart import Cart, CartItem
from app.database.models.purchase_intent import PurchaseIntent
from app.database.models.policy import Policy
from app.database.models.recommendation import Recommendation
from app.database.models.revenue_opportunity import RevenueOpportunity
from app.database.models.payment_transaction import PaymentTransaction
from app.database.models.transaction_authorization import TransactionAuthorization
from app.database.models.approval_request import ApprovalRequest
from app.database.models.audit_event import AuditEvent
from app.database.models.agent_trace import AgentTrace

client = TestClient(app)

def test_complete_cross_tenant_isolation_and_idor_prevention(client, db):
    """
    Comprehensive Tenant Isolation & IDOR Audit:
    Verifies that Merchant A's resources can NEVER be retrieved, modified, approved,
    reconciled, or executed by Merchant B simply by manipulating IDs.
    """
    # 1. Setup Merchant A & Merchant B with admin users
    merchantA = Merchant(name="Tenant Alpha", domain="alpha.test", is_active=True)
    merchantB = Merchant(name="Tenant Beta", domain="beta.test", is_active=True)
    db.add_all([merchantA, merchantB])
    db.commit()
    db.refresh(merchantA)
    db.refresh(merchantB)

    from app.database.models.user import User
    from app.core.security import get_password_hash, create_access_token
    userA = User(email="admin@alpha.test", full_name="Alpha Admin", hashed_password=get_password_hash("pass123"), role="admin", merchant_id=merchantA.id, is_active=True)
    userB = User(email="admin@beta.test", full_name="Beta Admin", hashed_password=get_password_hash("pass123"), role="admin", merchant_id=merchantB.id, is_active=True)
    db.add_all([userA, userB])
    db.commit()

    tokenA = create_access_token(subject=userA.id, merchant_id=merchantA.id, role="admin")
    tokenB = create_access_token(subject=userB.id, merchant_id=merchantB.id, role="admin")
    headersA = {"Authorization": f"Bearer {tokenA}"}
    headersB = {"Authorization": f"Bearer {tokenB}"}

    # 2. Setup Resources for Merchant A
    prodA = Product(merchant_id=merchantA.id, name="Alpha Shoes", price=Decimal("2500.00"), category="Footwear", is_active=True)
    db.add(prodA)
    db.flush()
    db.add(Inventory(merchant_id=merchantA.id, product_id=prodA.id, stock_quantity=20))

    cartA = Cart(merchant_id=merchantA.id, session_id="sess_alpha_001", currency="INR", total_amount=Decimal("2500.00"))
    db.add(cartA)
    db.flush()
    db.add(CartItem(cart_id=cartA.id, product_id=prodA.id, quantity=1, unit_price_snapshot=Decimal("2500.00")))

    piA = PurchaseIntent(
        merchant_id=merchantA.id,
        buyer_id="buyer_alpha",
        session_id="sess_alpha_001",
        cart_id=cartA.id,
        status="CREATED",
        currency="INR",
        requested_amount=Decimal("2500.00"),
        product_summary={"items": [{"product_id": prodA.id, "name": prodA.name, "quantity": 1, "unit_price": "2500.00", "subtotal": "2500.00"}]},
        trace_id="trc_alpha_pi_001"
    )
    db.add(piA)
    recA = Recommendation(
        merchant_id=merchantA.id,
        session_id="sess_alpha_001",
        type="CROSS_SELL",
        recommended_product_id=prodA.id,
        reason="Alpha Test Cross Sell",
        confidence=0.85,
        status="PENDING",
        trace_id="trc_alpha_rec_001"
    )
    db.add(recA)
    policyA = Policy(
        merchant_id=merchantA.id,
        version=1,
        max_discount_percent=Decimal("10.00"),
        approval_threshold=Decimal("1000.00"), # Will trigger REQUIRES_APPROVAL for ₹2,500
        max_quantity=5,
        allowed_currency="INR",
        is_active=True
    )
    db.add(policyA)
    db.commit()

    # Evaluate intent to generate real DB-backed authorization & approval
    res_eval = client.post(f"/api/v1/purchase-intents/{piA.id}/evaluate?merchant_id={merchantA.id}", headers=headersA)
    assert res_eval.status_code == 200
    eval_data = res_eval.json()
    assert eval_data["decision"] == "REQUIRES_APPROVAL"

    apprA = db.query(ApprovalRequest).filter(ApprovalRequest.merchant_id == merchantA.id).first()
    assert apprA is not None

    # Approve approval request to mint valid authorization
    res_appr = client.post(f"/api/v1/approvals/{apprA.id}/approve?merchant_id={merchantA.id}", json={
        "reason": "Alpha Operator Approval"
    }, headers=headersA)
    assert res_appr.status_code == 200
    auth_id = res_appr.json()["authorization"]["id"]

    txA = PaymentTransaction(
        merchant_id=merchantA.id,
        purchase_intent_id=piA.id,
        authorization_id=auth_id,
        amount=Decimal("2500.00"),
        currency="INR",
        status="ORDER_CREATED",
        idempotency_key="idemp_alpha_001",
        receipt="rcpt_alpha_001"
    )
    db.add(txA)
    db.flush()

    oppA = RevenueOpportunity(
        merchant_id=merchantA.id,
        type="CAMPAIGN",
        source_product_id=prodA.id,
        target_product_ids=[prodA.id],
        title="Alpha Flash Sale",
        description="Alpha 5% campaign",
        reason="Testing",
        proposed_discount_percent=Decimal("5.00"),
        status="GENERATED",
        trace_id="trc_alpha_opp_001"
    )
    db.add(oppA)
    db.commit()

    # =========================================================================
    # VERIFY MERCHANT B CANNOT ACCESS MERCHANT A'S OBJECTS (IDOR CHECKS)
    # =========================================================================

    # 1. Purchase Intent Cross-Tenant Check
    res_pi = client.get(f"/api/v1/purchase-intents/{piA.id}?merchant_id={merchantB.id}", headers=headersB)
    assert res_pi.status_code == 404, "Merchant B should not view Merchant A's purchase intent"

    # 2. Purchase Intent Evaluation Cross-Tenant Check
    res_pi_eval = client.post(f"/api/v1/purchase-intents/{piA.id}/evaluate?merchant_id={merchantB.id}", headers=headersB)
    assert res_pi_eval.status_code in (400, 404), "Merchant B cannot evaluate Merchant A's intent"

    # 3. AI Recommendation Cross-Tenant Check
    res_rec = client.get(f"/api/v1/ai/recommendations/{recA.id}?merchant_id={merchantB.id}", headers=headersB)
    assert res_rec.status_code == 404, "Merchant B cannot view Merchant A's recommendation"

    res_rec_acc = client.post(f"/api/v1/ai/recommendations/{recA.id}/accept?merchant_id={merchantB.id}", headers=headersB)
    assert res_rec_acc.status_code == 404, "Merchant B cannot accept Merchant A's recommendation"

    # 4. Human Approval Cross-Tenant Check
    res_appr_get = client.get(f"/api/v1/approvals/{apprA.id}?merchant_id={merchantB.id}", headers=headersB)
    assert res_appr_get.status_code == 404, "Merchant B cannot view Merchant A's approval request"

    res_appr_post = client.post(f"/api/v1/approvals/{apprA.id}/approve?merchant_id={merchantB.id}", json={
        "reason": "Unauthorized approval attempt"
    }, headers=headersB)
    assert res_appr_post.status_code in (400, 404), "Merchant B cannot approve Merchant A's transaction"

    # 5. Payment Transaction Cross-Tenant Check
    res_tx_get = client.get(f"/api/v1/payments/{txA.id}?merchant_id={merchantB.id}", headers=headersB)
    assert res_tx_get.status_code in (400, 404), "Merchant B cannot view Merchant A's payment transaction"

    res_tx_recon = client.post(f"/api/v1/payments/{txA.id}/reconcile?merchant_id={merchantB.id}", headers=headersB)
    assert res_tx_recon.status_code in (400, 404), "Merchant B cannot reconcile Merchant A's payment transaction"

    # 6. Revenue Opportunity Cross-Tenant Check
    res_opp_get = client.get(f"/api/v1/revenue/opportunities/{oppA.id}?merchant_id={merchantB.id}", headers=headersB)
    assert res_opp_get.status_code == 404, "Merchant B cannot view Merchant A's revenue opportunity"

    res_opp_appr = client.post(f"/api/v1/revenue/opportunities/{oppA.id}/approve?merchant_id={merchantB.id}", json={
        "reason": "Unauthorized"
    }, headers=headersB)
    assert res_opp_appr.status_code == 404, "Merchant B cannot approve Merchant A's revenue opportunity"

    res_opp_exec = client.post(f"/api/v1/revenue/opportunities/{oppA.id}/execute?merchant_id={merchantB.id}", json={
        "idempotency_key": "idemp_cross_exec_001"
    }, headers=headersB)
    assert res_opp_exec.status_code == 404, "Merchant B cannot execute Merchant A's revenue opportunity"

    # 7. Audit Trace Cross-Tenant Check
    res_audit = client.get(f"/api/v1/audit/traces/trc_alpha_pi_001?merchant_id={merchantB.id}", headers=headersB)
    assert res_audit.status_code == 404, "Merchant B cannot view Merchant A's audit trace"
