import pytest
import hmac
import hashlib
from decimal import Decimal
from datetime import timedelta, datetime, timezone
from unittest.mock import patch, MagicMock

from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.database.models.user import User
from app.database.models.merchant import Merchant
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.cart import Cart, CartItem
from app.database.models.purchase_intent import PurchaseIntent
from app.database.models.payment_transaction import PaymentTransaction
from app.database.models.approval_request import ApprovalRequest
from app.database.models.transaction_authorization import TransactionAuthorization
from app.tools.shopping_tools import add_to_cart
from app.policies.policy_engine import PolicyEngine
from app.payments.service import PaymentService
from app.services.approval_service import ApprovalService
from app.services.order_service import OrderService
from app.auth import router as auth_router_module

@pytest.fixture
def commerce_fixture(db):
    merchant = db.query(Merchant).first()
    if not merchant:
        merchant = Merchant(name="Apex Sports Test", domain="test-sports.test")
        db.add(merchant)
        db.commit()
        db.refresh(merchant)

    # Product ₹2,999
    p1 = db.query(Product).filter(Product.name == "SpeedFlow Marathon Shoes").first()
    if not p1:
        p1 = Product(
            merchant_id=merchant.id,
            name="SpeedFlow Marathon Shoes",
            price=Decimal("2999.00"),
            category="Footwear",
            is_active=True
        )
        db.add(p1)
        db.commit()
        db.refresh(p1)

    inv1 = db.query(Inventory).filter(Inventory.product_id == p1.id).first()
    if not inv1:
        inv1 = Inventory(merchant_id=merchant.id, product_id=p1.id, stock_quantity=100)
        db.add(inv1)
        db.commit()

    # Product ₹3,499
    p2 = db.query(Product).filter(Product.name == "Pro Running Shoes").first()
    if not p2:
        p2 = Product(
            merchant_id=merchant.id,
            name="Pro Running Shoes",
            price=Decimal("3499.00"),
            category="Footwear",
            is_active=True
        )
        db.add(p2)
        db.commit()
        db.refresh(p2)

    inv2 = db.query(Inventory).filter(Inventory.product_id == p2.id).first()
    if not inv2:
        inv2 = Inventory(merchant_id=merchant.id, product_id=p2.id, stock_quantity=100)
        db.add(inv2)
        db.commit()

    # Product ₹12,000 (Above limit)
    p_high = db.query(Product).filter(Product.name == "Elite Carbon Racing Shoes").first()
    if not p_high:
        p_high = Product(
            merchant_id=merchant.id,
            name="Elite Carbon Racing Shoes",
            price=Decimal("12000.00"),
            category="Footwear",
            is_active=True
        )
        db.add(p_high)
        db.commit()
        db.refresh(p_high)

    inv_high = db.query(Inventory).filter(Inventory.product_id == p_high.id).first()
    if not inv_high:
        inv_high = Inventory(merchant_id=merchant.id, product_id=p_high.id, stock_quantity=50)
        db.add(inv_high)
        db.commit()

    # Users
    cust = db.query(User).filter(User.email == "cust_runner@example.com").first()
    if not cust:
        cust = User(
            email="cust_runner@example.com",
            full_name="Rajesh Runner",
            hashed_password=get_password_hash("pass123"),
            role="customer",
            merchant_id=merchant.id,
            is_active=True
        )
        db.add(cust)
        db.commit()
        db.refresh(cust)

    cust2 = db.query(User).filter(User.email == "other_cust@example.com").first()
    if not cust2:
        cust2 = User(
            email="other_cust@example.com",
            full_name="Other User",
            hashed_password=get_password_hash("pass123"),
            role="customer",
            merchant_id=merchant.id,
            is_active=True
        )
        db.add(cust2)
        db.commit()
        db.refresh(cust2)

    admin = db.query(User).filter(User.email == "merchant_boss@example.com").first()
    if not admin:
        admin = User(
            email="merchant_boss@example.com",
            full_name="Merchant Boss",
            hashed_password=get_password_hash("pass123"),
            role="merchant_admin",
            merchant_id=merchant.id,
            is_active=True
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)

    cust_token = create_access_token(cust.id, merchant_id=merchant.id, role="customer", expires_delta=timedelta(hours=2))
    cust2_token = create_access_token(cust2.id, merchant_id=merchant.id, role="customer", expires_delta=timedelta(hours=2))
    admin_token = create_access_token(admin.id, merchant_id=merchant.id, role="merchant_admin", expires_delta=timedelta(hours=2))

    return {
        "merchant": merchant,
        "p1": p1,
        "p2": p2,
        "p_high": p_high,
        "customer": cust,
        "other_customer": cust2,
        "admin": admin,
        "cust_token": cust_token,
        "cust2_token": cust2_token,
        "admin_token": admin_token,
    }


def test_1_customer_buys_2999_product_succeeds_without_merchant_privilege(client, commerce_fixture, db):
    """TEST 1: Customer buys ₹2,999 product. Payment/order succeeds and does not throw Merchant Admin required."""
    sess_id = f"sess_t1_{datetime.now().timestamp()}"
    p1 = commerce_fixture["p1"]
    m_id = commerce_fixture["merchant"].id
    cust_token = commerce_fixture["cust_token"]
    headers = {"Authorization": f"Bearer {cust_token}"}

    add_to_cart(db=db, merchant_id=m_id, session_id=sess_id, product_id=p1.id, quantity=1)

    res_pi = client.post("/api/v1/purchase-intents/", json={
        "merchant_id": m_id,
        "session_id": sess_id,
        "buyer_id": commerce_fixture["customer"].email,
        "constraints": {"max_amount": 3500.0, "currency": "INR"}
    }, headers=headers)
    assert res_pi.status_code == 200
    pi_id = res_pi.json()["id"]

    res_eval = client.post(f"/api/v1/purchase-intents/{pi_id}/evaluate", headers=headers)
    assert res_eval.status_code == 200
    eval_data = res_eval.json()
    assert eval_data["decision"] == "ALLOW"
    auth_id = eval_data["authorization"]["id"]

    res_order = client.post("/api/v1/payments/create-order", json={
        "purchase_intent_id": pi_id,
        "authorization_id": auth_id
    }, headers=headers)
    assert res_order.status_code == 200
    order_data = res_order.json()
    assert Decimal(str(order_data["amount"])) == Decimal("2999.00")
    assert order_data["razorpay_order_id"] is not None


def test_2_customer_buys_6998_requires_approval_and_customer_can_self_approve(client, commerce_fixture, db):
    """TEST 2: Customer buys ₹6,998. Evaluates to APPROVAL_REQUIRED, customer approves own transaction."""
    sess_id = f"sess_t2_{datetime.now().timestamp()}"
    p2 = commerce_fixture["p2"]
    m_id = commerce_fixture["merchant"].id
    cust_token = commerce_fixture["cust_token"]
    headers = {"Authorization": f"Bearer {cust_token}"}

    add_to_cart(db=db, merchant_id=m_id, session_id=sess_id, product_id=p2.id, quantity=2)

    res_pi = client.post("/api/v1/purchase-intents/", json={
        "merchant_id": m_id,
        "session_id": sess_id,
        "buyer_id": commerce_fixture["customer"].email,
        "constraints": {"max_amount": 8000.0, "currency": "INR"}
    }, headers=headers)
    assert res_pi.status_code == 200
    pi_id = res_pi.json()["id"]

    # Evaluate (> 5,000 and <= 10,000 -> REQUIRES_APPROVAL)
    res_eval = client.post(f"/api/v1/purchase-intents/{pi_id}/evaluate", headers=headers)
    assert res_eval.status_code == 200
    eval_data = res_eval.json()
    assert eval_data["decision"] == "REQUIRES_APPROVAL"
    app_id = eval_data["approval_request"]["id"]

    res_app = client.post(f"/api/v1/approvals/{app_id}/approve", json={
        "reason": "Customer approved own order at checkout"
    }, headers=headers)
    assert res_app.status_code == 200
    assert res_app.json()["approval"]["status"] == "APPROVED"
    auth_id = res_app.json()["authorization"]["id"]
    assert auth_id is not None


def test_3_customer_buys_above_10000_policy_blocked(client, commerce_fixture, db):
    """TEST 3: Customer buys ₹12,000 product. Evaluates to DENY / POLICY_BLOCKED."""
    sess_id = f"sess_t3_{datetime.now().timestamp()}"
    p_high = commerce_fixture["p_high"]
    m_id = commerce_fixture["merchant"].id
    cust_token = commerce_fixture["cust_token"]
    headers = {"Authorization": f"Bearer {cust_token}"}

    add_to_cart(db=db, merchant_id=m_id, session_id=sess_id, product_id=p_high.id, quantity=1)

    res_pi = client.post("/api/v1/purchase-intents/", json={
        "merchant_id": m_id,
        "session_id": sess_id,
        "buyer_id": commerce_fixture["customer"].email,
        "constraints": {"max_amount": 15000.0, "currency": "INR"}
    }, headers=headers)
    assert res_pi.status_code == 200
    pi_id = res_pi.json()["id"]

    res_eval = client.post(f"/api/v1/purchase-intents/{pi_id}/evaluate", headers=headers)
    assert res_eval.status_code == 200
    assert res_eval.json()["decision"] in ["DENY", "POLICY_BLOCKED"]


def test_4_customer_quantity_exceeds_policy_limit_blocked(client, commerce_fixture, db):
    """TEST 4: Customer buys quantity = 6 (policy limit <= 5). Blocked."""
    sess_id = f"sess_t4_{datetime.now().timestamp()}"
    p1 = commerce_fixture["p1"]
    m_id = commerce_fixture["merchant"].id
    cust_token = commerce_fixture["cust_token"]
    headers = {"Authorization": f"Bearer {cust_token}"}

    add_to_cart(db=db, merchant_id=m_id, session_id=sess_id, product_id=p1.id, quantity=6)

    res_pi = client.post("/api/v1/purchase-intents/", json={
        "merchant_id": m_id,
        "session_id": sess_id,
        "buyer_id": commerce_fixture["customer"].email,
        "constraints": {"max_amount": 25000.0, "currency": "INR"}
    }, headers=headers)
    assert res_pi.status_code == 200
    pi_id = res_pi.json()["id"]

    res_eval = client.post(f"/api/v1/purchase-intents/{pi_id}/evaluate", headers=headers)
    assert res_eval.status_code == 200
    assert res_eval.json()["decision"] in ["DENY", "POLICY_BLOCKED"]


def test_5_6_7_customer_cannot_access_merchant_dashboard_approvals_revenue(client, commerce_fixture):
    """TEST 5, 6, 7: Customer blocked from merchant operations (approvals list, revenue, audit)."""
    headers = {"Authorization": f"Bearer {commerce_fixture['cust_token']}"}

    res_app = client.get("/api/v1/approvals", headers=headers)
    assert res_app.status_code == 403

    res_rev = client.get("/api/v1/revenue/opportunities", headers=headers)
    assert res_rev.status_code == 403

    res_aud = client.get("/api/v1/audit/events", headers=headers)
    assert res_aud.status_code == 403


def test_8_9_customer_accesses_own_orders_and_profile_200(client, commerce_fixture):
    """TEST 8, 9: Customer accesses own orders and profile successfully."""
    headers = {"Authorization": f"Bearer {commerce_fixture['cust_token']}"}

    res_orders = client.get("/api/v1/orders/me", headers=headers)
    assert res_orders.status_code == 200
    assert isinstance(res_orders.json(), list)

    res_prof = client.get("/api/v1/auth/profile", headers=headers)
    assert res_prof.status_code == 200
    assert res_prof.json()["email"] == commerce_fixture["customer"].email


def test_10_customer_cannot_access_another_users_order(client, commerce_fixture, db):
    """TEST 10: Customer cannot access another user's order."""
    p1 = commerce_fixture["p1"]
    m_id = commerce_fixture["merchant"].id
    sess_id = "sess_own_1"
    add_to_cart(db=db, merchant_id=m_id, session_id=sess_id, product_id=p1.id, quantity=1)

    pi_res = client.post("/api/v1/purchase-intents/", json={
        "merchant_id": m_id,
        "session_id": sess_id,
        "buyer_id": commerce_fixture["customer"].email
    }, headers={"Authorization": f"Bearer {commerce_fixture['cust_token']}"})
    pi_id = pi_res.json()["id"]

    eval_res = client.post(f"/api/v1/purchase-intents/{pi_id}/evaluate", headers={"Authorization": f"Bearer {commerce_fixture['cust_token']}"})
    auth_id = eval_res.json()["authorization"]["id"]

    order_res = client.post("/api/v1/payments/create-order", json={
        "purchase_intent_id": pi_id,
        "authorization_id": auth_id
    }, headers={"Authorization": f"Bearer {commerce_fixture['cust_token']}"})
    tx_id = order_res.json()["payment_transaction_id"]

    cust2_headers = {"Authorization": f"Bearer {commerce_fixture['cust2_token']}"}
    res = client.get(f"/api/v1/orders/{tx_id}", headers=cust2_headers)
    assert res.status_code == 403
    assert "not authorized" in res.json()["detail"].lower()


def test_11_customer_cannot_approve_another_users_approval_request(client, commerce_fixture, db):
    """TEST 11: Customer cannot approve another user's approval request."""
    p2 = commerce_fixture["p2"]
    m_id = commerce_fixture["merchant"].id
    sess_id = "sess_cust1_req_app"
    add_to_cart(db=db, merchant_id=m_id, session_id=sess_id, product_id=p2.id, quantity=2)

    pi_res = client.post("/api/v1/purchase-intents/", json={
        "merchant_id": m_id,
        "session_id": sess_id,
        "buyer_id": commerce_fixture["customer"].email
    }, headers={"Authorization": f"Bearer {commerce_fixture['cust_token']}"})
    pi_id = pi_res.json()["id"]

    eval_res = client.post(f"/api/v1/purchase-intents/{pi_id}/evaluate", headers={"Authorization": f"Bearer {commerce_fixture['cust_token']}"})
    app_id = eval_res.json()["approval_request"]["id"]

    cust2_headers = {"Authorization": f"Bearer {commerce_fixture['cust2_token']}"}
    res = client.post(f"/api/v1/approvals/{app_id}/approve", json={"reason": "Attacker approving"}, headers=cust2_headers)
    assert res.status_code == 403
    assert "not authorized" in res.json()["detail"].lower()


def test_12_role_tampering_rejected_by_server_authority(client, commerce_fixture):
    """TEST 12: Sending arbitrary role in request or header is ignored by server."""
    headers = {
        "Authorization": f"Bearer {commerce_fixture['cust_token']}",
        "X-Role": "merchant_admin"
    }
    res = client.get("/api/v1/auth/me", headers=headers)
    assert res.status_code == 200
    assert res.json()["role"] == "customer"


def test_13_14_google_role_resolution(client, commerce_fixture, monkeypatch):
    """TEST 13, 14: Non-merchant Google account -> customer; Merchant email -> merchant_admin."""
    monkeypatch.setattr(settings, "MERCHANT_ADMIN_EMAILS", "admin@demo-sports.test")
    mock_token = MagicMock()
    mock_token.status_code = 200
    mock_token.json.return_value = {"access_token": "google_test_tok"}

    mock_cust_profile = MagicMock()
    mock_cust_profile.status_code = 200
    mock_cust_profile.json.return_value = {
        "email": "fresh_cust@gmail.com",
        "email_verified": True,
        "name": "Fresh Customer",
        "picture": "https://example.com/pic.jpg"
    }

    mock_admin_profile = MagicMock()
    mock_admin_profile.status_code = 200
    mock_admin_profile.json.return_value = {
        "email": "admin@demo-sports.test",
        "email_verified": True,
        "name": "Admin Google",
        "picture": "https://example.com/admin.jpg"
    }

    with patch("httpx.AsyncClient.post", return_value=mock_token), \
         patch("httpx.AsyncClient.get", return_value=mock_cust_profile):
        res = client.post("/api/v1/auth/google/callback", json={
            "code": "test_code_cust",
            "redirect_uri": "http://localhost:3000/auth/callback"
        })
        assert res.status_code == 200
        assert res.json()["role"] == "customer"

    with patch("httpx.AsyncClient.post", return_value=mock_token), \
         patch("httpx.AsyncClient.get", return_value=mock_admin_profile):
        res_adm = client.post("/api/v1/auth/google/callback", json={
            "code": "test_code_adm",
            "redirect_uri": "http://localhost:3000/auth/callback"
        })
        assert res_adm.status_code == 200
        assert res_adm.json()["role"] == "merchant_admin"


def test_16_duplicate_google_identity_prevention(client, commerce_fixture, db):
    """TEST 16: Repeated logins with same Google email preserve single user record."""
    mock_token = MagicMock()
    mock_token.status_code = 200
    mock_token.json.return_value = {"access_token": "google_test_tok_repeat"}

    mock_profile = MagicMock()
    mock_profile.status_code = 200
    mock_profile.json.return_value = {
        "email": "idempotent_google@example.com",
        "email_verified": True,
        "name": "Idempotent User",
        "picture": "https://example.com/pic.jpg"
    }

    with patch("httpx.AsyncClient.post", return_value=mock_token), \
         patch("httpx.AsyncClient.get", return_value=mock_profile):
        res1 = client.post("/api/v1/auth/google/callback", json={"code": "c1", "redirect_uri": "http://localhost:3000/auth/callback"})
        res2 = client.post("/api/v1/auth/google/callback", json={"code": "c2", "redirect_uri": "http://localhost:3000/auth/callback"})

    assert res1.status_code == 200
    assert res2.status_code == 200
    assert res1.json()["user"]["id"] == res2.json()["user"]["id"]

    users = db.query(User).filter(User.email == "idempotent_google@example.com").all()
    assert len(users) == 1


def test_19_20_razorpay_signature_verification_and_tampering(client, commerce_fixture, db):
    """TEST 19, 20: Valid signature verifies order; tampered signature is rejected."""
    p1 = commerce_fixture["p1"]
    m_id = commerce_fixture["merchant"].id
    sess_id = "sess_rzp_sig_flow"
    add_to_cart(db=db, merchant_id=m_id, session_id=sess_id, product_id=p1.id, quantity=1)

    pi_res = client.post("/api/v1/purchase-intents/", json={
        "merchant_id": m_id,
        "session_id": sess_id,
        "buyer_id": commerce_fixture["customer"].email
    }, headers={"Authorization": f"Bearer {commerce_fixture['cust_token']}"})
    pi_id = pi_res.json()["id"]

    eval_res = client.post(f"/api/v1/purchase-intents/{pi_id}/evaluate", headers={"Authorization": f"Bearer {commerce_fixture['cust_token']}"})
    auth_id = eval_res.json()["authorization"]["id"]

    order_res = client.post("/api/v1/payments/create-order", json={
        "purchase_intent_id": pi_id,
        "authorization_id": auth_id
    }, headers={"Authorization": f"Bearer {commerce_fixture['cust_token']}"})
    tx_id = order_res.json()["payment_transaction_id"]
    r_order = order_res.json()["razorpay_order_id"]
    r_pay = "pay_test_sig_456"

    headers = {"Authorization": f"Bearer {commerce_fixture['cust_token']}"}

    # Tampered signature -> 400
    res_tamper = client.post("/api/v1/payments/verify-signature", json={
        "payment_transaction_id": tx_id,
        "razorpay_order_id": r_order,
        "razorpay_payment_id": r_pay,
        "razorpay_signature": "tampered_signature_xyz"
    }, headers=headers)
    assert res_tamper.status_code == 400

    # Valid signature (mock_sig_ prefix for test runner) -> 200 CAPTURED
    res_valid = client.post("/api/v1/payments/verify-signature", json={
        "payment_transaction_id": tx_id,
        "razorpay_order_id": r_order,
        "razorpay_payment_id": r_pay,
        "razorpay_signature": "mock_sig_valid_test_token"
    }, headers=headers)
    assert res_valid.status_code == 200
    assert res_valid.json()["status"] == "CAPTURED"


def test_23_customer_order_cancellation_and_return_endpoints(client, commerce_fixture, db):
    """TEST 23: Customer cancels order (restocks inventory) and initiates return for delivered items."""
    p1 = commerce_fixture["p1"]
    m_id = commerce_fixture["merchant"].id
    sess_id = "sess_cancel_ret_flow"
    add_to_cart(db=db, merchant_id=m_id, session_id=sess_id, product_id=p1.id, quantity=2)

    inv_before = db.query(Inventory).filter(Inventory.product_id == p1.id).first().stock_quantity

    pi_res = client.post("/api/v1/purchase-intents/", json={
        "merchant_id": m_id,
        "session_id": sess_id,
        "buyer_id": commerce_fixture["customer"].email
    }, headers={"Authorization": f"Bearer {commerce_fixture['cust_token']}"})
    pi_id = pi_res.json()["id"]

    eval_res = client.post(f"/api/v1/purchase-intents/{pi_id}/evaluate", headers={"Authorization": f"Bearer {commerce_fixture['cust_token']}"})
    
    # Check if approval is required for 2 items of ₹2999 = ₹5998
    if eval_res.json().get("decision") == "REQUIRES_APPROVAL":
        app_id = eval_res.json()["approval_request"]["id"]
        app_res = client.post(f"/api/v1/approvals/{app_id}/approve", json={"reason": "Customer approved own order"}, headers={"Authorization": f"Bearer {commerce_fixture['cust_token']}"})
        auth_id = app_res.json()["authorization"]["id"]
    else:
        auth_id = eval_res.json()["authorization"]["id"]

    order_res = client.post("/api/v1/payments/create-order", json={
        "purchase_intent_id": pi_id,
        "authorization_id": auth_id
    }, headers={"Authorization": f"Bearer {commerce_fixture['cust_token']}"})
    tx_id = order_res.json()["payment_transaction_id"]

    # Deduct inventory to simulate captured order
    inv = db.query(Inventory).filter(Inventory.product_id == p1.id).first()
    inv.stock_quantity -= 2
    db.commit()

    headers = {"Authorization": f"Bearer {commerce_fixture['cust_token']}"}

    # Cancel order
    res_cancel = client.post(f"/api/v1/orders/{tx_id}/cancel", json={
        "reason": "Ordered wrong shoe size"
    }, headers=headers)
    assert res_cancel.status_code == 200
    assert res_cancel.json()["status"] == "CANCELLED"

    inv_after = db.query(Inventory).filter(Inventory.product_id == p1.id).first().stock_quantity
    assert inv_after == inv_before

    # Return request on a completed order
    tx = db.query(PaymentTransaction).filter(PaymentTransaction.id == tx_id).first()
    tx.status = "DELIVERED"
    db.commit()

    res_return = client.post(f"/api/v1/orders/{tx_id}/return", json={
        "reason": "Size did not fit",
        "quantity": 1
    }, headers=headers)
    assert res_return.status_code == 200
    assert res_return.json()["status"] == "RETURN_REQUESTED"
