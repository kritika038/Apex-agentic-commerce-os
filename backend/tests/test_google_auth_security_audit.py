import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.database.models.merchant import Merchant
from app.database.models.user import User
from app.core.security import create_access_token
from app.auth import router as auth_router_module

class _MockGoogleAsyncClient:
    def __init__(self, userinfo_payload: dict):
        self.userinfo_payload = userinfo_payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, data=None):
        class _Resp:
            status_code = 200
            def json(self):
                return {"access_token": "fake_google_token"}
        return _Resp()

    async def get(self, url, headers=None):
        class _Resp:
            status_code = 200
            def json(self_inner):
                return self.userinfo_payload
        return _Resp()

@pytest.fixture
def test_security_merchant(db: Session):
    m = Merchant(name="Apex Sports Store", domain="apex-sports.test", is_active=True)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m

def test_case_a_normal_google_user_selecting_customer(monkeypatch, client, test_security_merchant, db):
    """CASE A: Normal Google account selecting Customer -> must receive CUSTOMER."""
    auth_router_module.settings.GOOGLE_CLIENT_ID = "test_client_id"
    auth_router_module.settings.GOOGLE_CLIENT_SECRET = "test_client_secret"
    auth_router_module.settings.MERCHANT_ADMIN_EMAILS = "authorized_merchant@apex.test"

    monkeypatch.setattr(
        auth_router_module.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _MockGoogleAsyncClient({
            "sub": "google_uid_normal_1",
            "email": "normal_shopper@gmail.com",
            "name": "Normal Shopper",
            "email_verified": True
        })
    )

    res = client.post("/api/v1/auth/google/callback", json={
        "code": "auth_code_case_a",
        "role": "customer"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["role"] == "customer"
    assert data["user"]["role"] == "customer"

    # Verify in DB
    user = db.query(User).filter(User.email == "normal_shopper@gmail.com").first()
    assert user is not None
    assert user.role == "customer"

def test_case_b_normal_google_user_selecting_merchant_denied_admin(monkeypatch, client, test_security_merchant, db):
    """CASE B: Normal Google account selecting Merchant tab -> MUST NOT receive MERCHANT_ADMIN."""
    auth_router_module.settings.GOOGLE_CLIENT_ID = "test_client_id"
    auth_router_module.settings.GOOGLE_CLIENT_SECRET = "test_client_secret"
    auth_router_module.settings.MERCHANT_ADMIN_EMAILS = "authorized_merchant@apex.test"

    monkeypatch.setattr(
        auth_router_module.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _MockGoogleAsyncClient({
            "sub": "google_uid_attacker_1",
            "email": "attacker_or_normal_user@gmail.com",
            "name": "Normal User Attempting Merchant",
            "email_verified": True
        })
    )

    # Client claims role="merchant_admin" in request payload
    res = client.post("/api/v1/auth/google/callback", json={
        "code": "auth_code_case_b",
        "role": "merchant_admin"
    })
    assert res.status_code == 200
    data = res.json()
    # Server-authoritative override: MUST be customer
    assert data["role"] == "customer"
    assert data["user"]["role"] == "customer"

    user = db.query(User).filter(User.email == "attacker_or_normal_user@gmail.com").first()
    assert user is not None
    assert user.role == "customer"

def test_case_c_authorized_merchant_receives_merchant_admin(monkeypatch, client, test_security_merchant, db):
    """CASE C: Authorized merchant Google account -> receives MERCHANT_ADMIN."""
    auth_router_module.settings.GOOGLE_CLIENT_ID = "test_client_id"
    auth_router_module.settings.GOOGLE_CLIENT_SECRET = "test_client_secret"
    auth_router_module.settings.MERCHANT_ADMIN_EMAILS = "authorized_merchant@apex.test"

    monkeypatch.setattr(
        auth_router_module.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _MockGoogleAsyncClient({
            "sub": "google_uid_merchant_1",
            "email": "authorized_merchant@apex.test",
            "name": "Apex Official Merchant",
            "email_verified": True
        })
    )

    res = client.post("/api/v1/auth/google/callback", json={
        "code": "auth_code_case_c",
        "role": "merchant_admin"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["role"] == "merchant_admin"
    assert data["user"]["role"] == "merchant_admin"

    user = db.query(User).filter(User.email == "authorized_merchant@apex.test").first()
    assert user.role == "merchant_admin"

def test_case_d_authorized_merchant_selecting_customer_preserves_security(monkeypatch, client, test_security_merchant, db):
    """CASE D: Authorized merchant Google account selecting customer intent -> server assigns authoritative merchant_admin."""
    auth_router_module.settings.GOOGLE_CLIENT_ID = "test_client_id"
    auth_router_module.settings.GOOGLE_CLIENT_SECRET = "test_client_secret"
    auth_router_module.settings.MERCHANT_ADMIN_EMAILS = "authorized_merchant@apex.test"

    monkeypatch.setattr(
        auth_router_module.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _MockGoogleAsyncClient({
            "sub": "google_uid_merchant_1",
            "email": "authorized_merchant@apex.test",
            "name": "Apex Official Merchant",
            "email_verified": True
        })
    )

    res = client.post("/api/v1/auth/google/callback", json={
        "code": "auth_code_case_d",
        "role": "customer"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["role"] == "merchant_admin"

def test_case_e_localstorage_tamper_rejected_by_auth_me(monkeypatch, client, test_security_merchant, db):
    """CASE E: LocalStorage role tampering is rejected by /auth/me."""
    auth_router_module.settings.GOOGLE_CLIENT_ID = "test_client_id"
    auth_router_module.settings.GOOGLE_CLIENT_SECRET = "test_client_secret"
    auth_router_module.settings.MERCHANT_ADMIN_EMAILS = "authorized_merchant@apex.test"

    monkeypatch.setattr(
        auth_router_module.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _MockGoogleAsyncClient({
            "sub": "google_uid_shopper_tamper",
            "email": "honest_customer@gmail.com",
            "name": "Honest Customer",
            "email_verified": True
        })
    )

    # Legitimate customer login
    login_res = client.post("/api/v1/auth/google/callback", json={"code": "code_tamper"})
    token = login_res.json()["access_token"]

    # Even if client tampers with localStorage/cookies, backend /auth/me returns ground truth
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["role"] == "customer"
    assert me_res.json()["role"] != "merchant_admin"

def test_case_f_and_g_merchant_apis_reject_customer_with_403(monkeypatch, client, test_security_merchant, db):
    """CASE F & G: Customer token accessing merchant-only APIs receives HTTP 403 Forbidden."""
    auth_router_module.settings.GOOGLE_CLIENT_ID = "test_client_id"
    auth_router_module.settings.GOOGLE_CLIENT_SECRET = "test_client_secret"
    auth_router_module.settings.MERCHANT_ADMIN_EMAILS = "authorized_merchant@apex.test"

    monkeypatch.setattr(
        auth_router_module.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _MockGoogleAsyncClient({
            "sub": "google_uid_shopper_403",
            "email": "customer_blocked@gmail.com",
            "name": "Customer Blocked",
            "email_verified": True
        })
    )

    login_res = client.post("/api/v1/auth/google/callback", json={"code": "code_403"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Test all merchant-only endpoints
    for endpoint in ["/api/v1/approvals", "/api/v1/policies", "/api/v1/audit/events", "/api/v1/revenue/overview"]:
        res = client.get(endpoint, headers=headers)
        assert res.status_code == 403, f"Endpoint {endpoint} should have returned 403 Forbidden for customer token, got {res.status_code}"

def test_case_h_and_i_logout_and_customer_relogin_isolation(monkeypatch, client, test_security_merchant, db):
    """CASE H & I: Logging out and logging in as customer strictly provides customer permissions."""
    auth_router_module.settings.GOOGLE_CLIENT_ID = "test_client_id"
    auth_router_module.settings.GOOGLE_CLIENT_SECRET = "test_client_secret"
    auth_router_module.settings.MERCHANT_ADMIN_EMAILS = "authorized_merchant@apex.test"

    # 1. Login as authorized merchant
    monkeypatch.setattr(
        auth_router_module.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _MockGoogleAsyncClient({
            "sub": "google_uid_merchant_hi",
            "email": "authorized_merchant@apex.test",
            "name": "Merchant HI",
            "email_verified": True
        })
    )
    m_res = client.post("/api/v1/auth/google/callback", json={"code": "code_m_hi"})
    m_token = m_res.json()["access_token"]
    assert client.get("/api/v1/approvals", headers={"Authorization": f"Bearer {m_token}"}).status_code == 200

    # 2. Re-login as normal customer
    monkeypatch.setattr(
        auth_router_module.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _MockGoogleAsyncClient({
            "sub": "google_uid_customer_hi",
            "email": "customer_hi@gmail.com",
            "name": "Customer HI",
            "email_verified": True
        })
    )
    c_res = client.post("/api/v1/auth/google/callback", json={"code": "code_c_hi"})
    c_token = c_res.json()["access_token"]

    # Customer token cannot access merchant approvals
    assert client.get("/api/v1/approvals", headers={"Authorization": f"Bearer {c_token}"}).status_code == 403
    # Customer profile works
    assert client.get("/api/v1/auth/profile", headers={"Authorization": f"Bearer {c_token}"}).status_code == 200

def test_duplicate_user_record_prevention(monkeypatch, client, test_security_merchant, db):
    """Calling Google callback multiple times for same identity updates existing record without duplicate creation."""
    auth_router_module.settings.GOOGLE_CLIENT_ID = "test_client_id"
    auth_router_module.settings.GOOGLE_CLIENT_SECRET = "test_client_secret"
    auth_router_module.settings.MERCHANT_ADMIN_EMAILS = "authorized_merchant@apex.test"

    monkeypatch.setattr(
        auth_router_module.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _MockGoogleAsyncClient({
            "sub": "google_uid_dup_1",
            "email": "repeat_user@gmail.com",
            "name": "Repeat User Initial",
            "email_verified": True
        })
    )

    client.post("/api/v1/auth/google/callback", json={"code": "code_dup_1"})
    count_1 = db.query(User).filter(User.email == "repeat_user@gmail.com").count()
    assert count_1 == 1

    monkeypatch.setattr(
        auth_router_module.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _MockGoogleAsyncClient({
            "sub": "google_uid_dup_1",
            "email": "repeat_user@gmail.com",
            "name": "Repeat User Updated Name",
            "email_verified": True
        })
    )

    client.post("/api/v1/auth/google/callback", json={"code": "code_dup_2"})
    count_2 = db.query(User).filter(User.email == "repeat_user@gmail.com").count()
    assert count_2 == 1

    user = db.query(User).filter(User.email == "repeat_user@gmail.com").first()
    assert user.full_name == "Repeat User Updated Name"
