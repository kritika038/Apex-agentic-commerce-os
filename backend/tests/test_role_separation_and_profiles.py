import pytest
from datetime import timedelta
from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.database.models.user import User
from app.database.models.merchant import Merchant
from app.database.models.purchase_intent import PurchaseIntent
from app.database.models.payment_transaction import PaymentTransaction
from app.database.models.rewards import CoinWallet
from app.auth import router as auth_router_module

@pytest.fixture
def role_test_setup(db):
    merchant = db.query(Merchant).first()
    if not merchant:
        merchant = Merchant(name="Apex Sports Test", domain="test-sports.test")
        db.add(merchant)
        db.commit()
        db.refresh(merchant)

    # Customer user
    cust = db.query(User).filter(User.email == "role_cust@example.com").first()
    if not cust:
        cust = User(
            email="role_cust@example.com",
            full_name="Alice Customer",
            hashed_password=get_password_hash("password123"),
            role="customer",
            merchant_id=merchant.id,
            is_active=True
        )
        db.add(cust)
        db.commit()
        db.refresh(cust)

    # Merchant admin user
    merchant_admin = db.query(User).filter(User.email == "role_admin@example.com").first()
    if not merchant_admin:
        merchant_admin = User(
            email="role_admin@example.com",
            full_name="Apex Administrator",
            hashed_password=get_password_hash("password123"),
            role="merchant_admin",
            merchant_id=merchant.id,
            is_active=True
        )
        db.add(merchant_admin)
        db.commit()
        db.refresh(merchant_admin)

    # Create tokens
    expires = timedelta(minutes=60)
    cust_token = create_access_token(cust.id, merchant_id=merchant.id, role="customer", expires_delta=expires)
    admin_token = create_access_token(merchant_admin.id, merchant_id=merchant.id, role="merchant_admin", expires_delta=expires)

    return {
        "merchant": merchant,
        "customer": cust,
        "merchant_admin": merchant_admin,
        "customer_token": cust_token,
        "admin_token": admin_token,
    }

def test_1_customer_auth_me_returns_customer(client, role_test_setup):
    headers = {"Authorization": f"Bearer {role_test_setup['customer_token']}"}
    res = client.get("/api/v1/auth/me", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["role"] == "customer"
    assert data["email"] == "role_cust@example.com"
    assert "created_at" in data

def test_2_merchant_auth_me_returns_merchant_admin(client, role_test_setup):
    headers = {"Authorization": f"Bearer {role_test_setup['admin_token']}"}
    res = client.get("/api/v1/auth/me", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["role"] == "merchant_admin"
    assert data["email"] == "role_admin@example.com"

def test_3_customer_cannot_access_merchant_apis_blocked_403(client, role_test_setup):
    cust_headers = {"Authorization": f"Bearer {role_test_setup['customer_token']}"}

    # 1. Revenue Opportunities
    res1 = client.get("/api/v1/revenue/opportunities", headers=cust_headers)
    assert res1.status_code == 403
    assert "Merchant Admin privileges required" in res1.json()["detail"]

    # 2. Approvals
    res2 = client.get("/api/v1/approvals", headers=cust_headers)
    assert res2.status_code == 403
    assert "Merchant Admin privileges required" in res2.json()["detail"]

    # 3. Policies
    res3 = client.get("/api/v1/policies", headers=cust_headers)
    assert res3.status_code == 403
    assert "Merchant Admin privileges required" in res3.json()["detail"]

    # 4. Audit Events
    res4 = client.get("/api/v1/audit/events", headers=cust_headers)
    assert res4.status_code == 403
    assert "Merchant Admin privileges required" in res4.json()["detail"]

    # 5. Merchant Profile
    res5 = client.get("/api/v1/auth/merchant-profile", headers=cust_headers)
    assert res5.status_code == 403
    assert "Merchant Admin privileges required" in res5.json()["detail"]

    # 6. Product Creation
    res6 = client.post("/api/v1/products/", headers=cust_headers, json={
        "name": "Hacked Shoe",
        "description": "Unauthorized",
        "price": 999.0,
        "category": "Shoes",
        "currency": "INR"
    })
    assert res6.status_code == 403

def test_4_merchant_can_access_merchant_apis(client, role_test_setup):
    admin_headers = {"Authorization": f"Bearer {role_test_setup['admin_token']}"}

    # 1. Approvals
    res1 = client.get("/api/v1/approvals", headers=admin_headers)
    assert res1.status_code == 200

    # 2. Policies
    res2 = client.get("/api/v1/policies", headers=admin_headers)
    assert res2.status_code == 200

    # 3. Audit Events
    res3 = client.get("/api/v1/audit/events", headers=admin_headers)
    assert res3.status_code == 200

    # 4. Merchant Profile
    res4 = client.get("/api/v1/auth/merchant-profile", headers=admin_headers)
    assert res4.status_code == 200
    data = res4.json()
    assert data["role"] == "merchant_admin"
    assert data["merchant_name"] == role_test_setup["merchant"].name
    assert "catalog_size" in data
    assert "total_gmv" in data
    assert data["governance"]["status"] == "ENFORCED"

def test_5_customer_profile_returns_current_customer_data_only(client, db, role_test_setup):
    cust = role_test_setup["customer"]
    merchant = role_test_setup["merchant"]

    # Add wallet and sample purchase intent for this customer
    wallet = CoinWallet(user_id=cust.id, balance=150)
    db.add(wallet)

    intent = PurchaseIntent(
        merchant_id=merchant.id,
        buyer_id=cust.id,
        session_id="sess_role_test_1",
        status="CONFIRMED",
        requested_amount=2999.0,
        currency="INR",
        cart_id="cart_test_role_1",
        delivery_address={"address_line1": "123 Sprint Way", "city": "Bengaluru", "state": "Karnataka", "pin_code": "560001"}
    )
    db.add(intent)
    db.flush()

    from app.database.models.policy import Policy
    from app.database.models.policy_evaluation import PolicyEvaluation
    from app.database.models.transaction_authorization import TransactionAuthorization
    import uuid
    from datetime import datetime, timezone

    pol = db.query(Policy).filter(Policy.merchant_id == merchant.id).first()
    if not pol:
        pol = Policy(merchant_id=merchant.id, version=1, approval_threshold=5000, max_transaction_amount=10000)
        db.add(pol)
        db.flush()

    eval_record = PolicyEvaluation(
        merchant_id=merchant.id,
        purchase_intent_id=intent.id,
        policy_id=pol.id,
        policy_version=1,
        decision="ALLOW",
        risk_level="LOW",
        violations=[]
    )
    db.add(eval_record)
    db.flush()

    auth_record = TransactionAuthorization(
        merchant_id=merchant.id,
        purchase_intent_id=intent.id,
        policy_evaluation_id=eval_record.id,
        policy_version=1,
        status="AUTHORIZED",
        authorized_amount=2999.0,
        currency="INR",
        authorized_by="POLICY_ENGINE_AUTO",
        expires_at=datetime.now(timezone.utc).replace(tzinfo=None)
    )
    db.add(auth_record)
    db.flush()

    tx = PaymentTransaction(
        merchant_id=merchant.id,
        purchase_intent_id=intent.id,
        authorization_id=auth_record.id,
        amount=2999.0,
        currency="INR",
        status="CAPTURED",
        idempotency_key=f"idemp_{uuid.uuid4()}",
        receipt="rcpt_role_test_1"
    )
    db.add(tx)
    db.commit()

    cust_headers = {"Authorization": f"Bearer {role_test_setup['customer_token']}"}
    res = client.get("/api/v1/auth/profile", headers=cust_headers)
    assert res.status_code == 200
    data = res.json()

    assert data["email"] == "role_cust@example.com"
    assert data["orders_count"] >= 1
    assert data["total_spent"] >= 2999.0
    assert data["apex_coins_balance"] == 150
    assert len(data["saved_addresses"]) >= 1
    assert data["saved_addresses"][0]["city"] == "Bengaluru"

def test_6_customer_profile_update_name(client, role_test_setup):
    cust_headers = {"Authorization": f"Bearer {role_test_setup['customer_token']}"}
    
    update_res = client.put("/api/v1/auth/profile", headers=cust_headers, json={"full_name": "Alice Runner Bansal"})
    assert update_res.status_code == 200
    assert update_res.json()["full_name"] == "Alice Runner Bansal"

    get_res = client.get("/api/v1/auth/profile", headers=cust_headers)
    assert get_res.json()["full_name"] == "Alice Runner Bansal"

class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload

class _FakeAsyncClient:
    def __init__(self, token_status: int = 200, userinfo_payload: dict = None):
        self.token_status = token_status
        self.userinfo_payload = userinfo_payload or {
            "sub": "google_123456",
            "email": "fresh_user@example.com",
            "name": "Fresh User",
            "email_verified": True
        }

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, data=None):
        return _FakeResponse(200, {"access_token": "google_access_token"})

    async def get(self, url, headers=None):
        return _FakeResponse(200, self.userinfo_payload)

def test_7_google_customer_login_gets_customer_role(monkeypatch, client, setup_test_data):
    auth_router_module.settings.GOOGLE_CLIENT_ID = "google-client-id"
    auth_router_module.settings.GOOGLE_CLIENT_SECRET = "google-client-secret"

    monkeypatch.setattr(
        auth_router_module.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _FakeAsyncClient(
            userinfo_payload={
                "sub": "google_new_cust_999",
                "email": "fresh_user@example.com",
                "name": "Fresh User",
                "email_verified": True
            }
        )
    )

    res = client.post("/api/v1/auth/google/callback", json={"code": "sample_code", "role": "merchant_admin"})
    assert res.status_code == 200
    # Even though frontend requested merchant_admin, server-authoritative logic forces customer because email is not allowlisted
    assert res.json()["role"] == "customer"
    assert res.json()["user"]["role"] == "customer"

def test_8_google_merchant_login_gets_merchant_role_only_through_server_authorization(monkeypatch, client, setup_test_data):
    auth_router_module.settings.GOOGLE_CLIENT_ID = "google-client-id"
    auth_router_module.settings.GOOGLE_CLIENT_SECRET = "google-client-secret"
    auth_router_module.settings.MERCHANT_ADMIN_EMAILS = "official_merchant@demo-sports.test"

    monkeypatch.setattr(
        auth_router_module.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _FakeAsyncClient(
            userinfo_payload={
                "sub": "google_merchant_999",
                "email": "official_merchant@demo-sports.test",
                "name": "Official Merchant",
                "email_verified": True
            }
        )
    )

    res = client.post("/api/v1/auth/google/callback", json={"code": "sample_code"})
    assert res.status_code == 200
    assert res.json()["role"] == "merchant_admin"
    assert res.json()["user"]["role"] == "merchant_admin"

def test_9_customer_cannot_modify_role_through_profile_api(client, role_test_setup):
    """Verifies that customer cannot escalate role via PUT /profile."""
    cust_headers = {"Authorization": f"Bearer {role_test_setup['customer_token']}"}
    # Even if attacker injects role in payload
    res = client.put("/api/v1/auth/profile", headers=cust_headers, json={"full_name": "Attacker", "role": "merchant_admin"})
    assert res.status_code == 200
    assert res.json()["role"] == "customer"
    
    # Confirm via /me
    me_res = client.get("/api/v1/auth/me", headers=cust_headers)
    assert me_res.json()["role"] == "customer"

def test_10_merchant_secret_credentials_never_returned_by_profile_apis(client, role_test_setup):
    """Verifies that secrets (Razorpay Key Secret, Google Client Secret, JWT secret) are NEVER leaked."""
    admin_headers = {"Authorization": f"Bearer {role_test_setup['admin_token']}"}
    res = client.get("/api/v1/auth/merchant-profile", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    
    # Ensure sensitive fields are completely absent
    assert "razorpay_key_secret" not in data
    assert "RAZORPAY_KEY_SECRET" not in data
    assert "google_client_secret" not in data
    assert "GOOGLE_CLIENT_SECRET" not in data
    assert "jwt_secret" not in data
    assert "JWT_SECRET_KEY" not in data
    assert "password" not in data
    assert "hashed_password" not in data
    
    # Safe status only
    assert "payment_status" in data
    assert "Razorpay" in data["payment_status"] or "Mock" in data["payment_status"]

def test_11_customer_profile_returns_active_vouchers_and_metrics(client, role_test_setup):
    """Verifies that customer profile returns active coupons, preferences, and real metrics."""
    cust_headers = {"Authorization": f"Bearer {role_test_setup['customer_token']}"}
    res = client.get("/api/v1/auth/profile", headers=cust_headers)
    assert res.status_code == 200
    data = res.json()
    
    assert "active_coupons" in data
    assert "preferences" in data
    assert "apex_coins_balance" in data
    assert "reward_points_balance" in data
    assert data["role"] == "customer"

def test_12_merchant_profile_returns_inventory_units_and_safe_payment_status(client, role_test_setup):
    """Verifies that merchant profile returns inventory units, safe payment status, and governance."""
    admin_headers = {"Authorization": f"Bearer {role_test_setup['admin_token']}"}
    res = client.get("/api/v1/auth/merchant-profile", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    
    assert data["role"] == "merchant_admin"
    assert "inventory_units" in data
    assert "catalog_size" in data
    assert "total_gmv" in data
    assert "merchant_auth_status" in data
    assert "Server Authorized" in data["merchant_auth_status"]
    assert data["governance"]["status"] == "ENFORCED"

def test_13_google_callback_invalid_grant_or_code(monkeypatch, client, setup_test_data):
    """Verifies that an invalid code or invalid grant returns HTTP 400 with safe message."""
    auth_router_module.settings.GOOGLE_CLIENT_ID = "google-client-id"
    auth_router_module.settings.GOOGLE_CLIENT_SECRET = "google-client-secret"

    class _FakeInvalidCodeClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return False
        async def post(self, url, data=None):
            return _FakeResponse(400, {"error": "invalid_grant", "error_description": "Bad Request"})

    monkeypatch.setattr(auth_router_module.httpx, "AsyncClient", lambda *args, **kwargs: _FakeInvalidCodeClient())

    res = client.post("/api/v1/auth/google/callback", json={"code": "expired_code"})
    assert res.status_code == 400
    assert "invalid or has expired" in res.json()["detail"]

def test_14_google_callback_invalid_redirect_uri_rejected(client, setup_test_data):
    """Verifies that unapproved redirect URIs are strictly rejected with HTTP 400."""
    auth_router_module.settings.GOOGLE_CLIENT_ID = "google-client-id"
    auth_router_module.settings.GOOGLE_CLIENT_SECRET = "google-client-secret"

    res = client.post("/api/v1/auth/google/callback", json={
        "code": "sample_code",
        "redirect_uri": "https://malicious-site.com/steal-token"
    })
    assert res.status_code == 400
    assert "redirect URI does not match" in res.json()["detail"]

def test_15_google_callback_unverified_email_rejected(monkeypatch, client, setup_test_data):
    """Verifies that Google accounts with unverified emails are rejected."""
    auth_router_module.settings.GOOGLE_CLIENT_ID = "google-client-id"
    auth_router_module.settings.GOOGLE_CLIENT_SECRET = "google-client-secret"

    monkeypatch.setattr(
        auth_router_module.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _FakeAsyncClient(
            userinfo_payload={
                "sub": "google_unverified_1",
                "email": "unverified@example.com",
                "name": "Unverified User",
                "email_verified": False
            }
        )
    )

    res = client.post("/api/v1/auth/google/callback", json={"code": "sample_code"})
    assert res.status_code == 400
    assert "email is not verified" in res.json()["detail"]

def test_16_duplicate_google_identity_prevention(monkeypatch, client, db, setup_test_data):
    """
    Verifies that repeated logins with the same Google email:
    - Finds the existing user
    - Does NOT create duplicate user records (user count for that email = 1)
    - Returns the same user.id across sessions
    """
    auth_router_module.settings.GOOGLE_CLIENT_ID = "google-client-id"
    auth_router_module.settings.GOOGLE_CLIENT_SECRET = "google-client-secret"

    monkeypatch.setattr(
        auth_router_module.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _FakeAsyncClient(
            userinfo_payload={
                "sub": "google_repeat_123",
                "email": "repeat_login@example.com",
                "name": "Repeat Customer",
                "email_verified": True
            }
        )
    )

    # First Login
    res1 = client.post("/api/v1/auth/google/callback", json={"code": "code_1"})
    assert res1.status_code == 200
    user_id_1 = res1.json()["user"]["id"]

    # Second Login (Same Google Account)
    res2 = client.post("/api/v1/auth/google/callback", json={"code": "code_2"})
    assert res2.status_code == 200
    user_id_2 = res2.json()["user"]["id"]

    assert user_id_1 == user_id_2

    # Verify DB user count for this email is strictly 1
    users = db.query(User).filter(User.email == "repeat_login@example.com").all()
    assert len(users) == 1

def test_17_normal_google_account_selecting_merchant_tab_is_blocked(monkeypatch, client, setup_test_data):
    """
    Verifies that a normal user selecting 'Merchant' tab during Google Sign-In
    is assigned 'customer' by the server and receives HTTP 403 on protected merchant APIs.
    """
    auth_router_module.settings.GOOGLE_CLIENT_ID = "google-client-id"
    auth_router_module.settings.GOOGLE_CLIENT_SECRET = "google-client-secret"

    monkeypatch.setattr(
        auth_router_module.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _FakeAsyncClient(
            userinfo_payload={
                "sub": "google_normal_user",
                "email": "normal_shopper@gmail.com",
                "name": "Normal Shopper",
                "email_verified": True
            }
        )
    )

    # User clicked "Merchant" tab -> frontend sent role="merchant_admin"
    res = client.post("/api/v1/auth/google/callback", json={"code": "code_normal", "role": "merchant_admin"})
    assert res.status_code == 200
    token = res.json()["access_token"]
    assert res.json()["role"] == "customer"

    # Verify token cannot access merchant console APIs
    auth_header = {"Authorization": f"Bearer {token}"}
    m_res = client.get("/api/v1/auth/merchant-profile", headers=auth_header)
    assert m_res.status_code == 403
    assert "Merchant Admin privileges required" in m_res.json()["detail"]

def test_18_unauthenticated_or_expired_token_handling(client):
    """Verifies that missing or invalid tokens return HTTP 401."""
    res1 = client.get("/api/v1/auth/me")
    assert res1.status_code == 401

    res2 = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid_token_12345"})
    assert res2.status_code == 401

