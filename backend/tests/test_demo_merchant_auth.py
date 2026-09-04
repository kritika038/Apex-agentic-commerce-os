import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database.session import SessionLocal
from app.database.models.user import User
from app.database.models.merchant import Merchant
from app.core.security import verify_password, get_password_hash, create_access_token
from scripts.seed import seed_db

client = TestClient(app)

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_demo_merchant_idempotent_seeding(db_session: Session):
    """Requirement 2, 3 & 8F: Seed idempotency ensures demo merchant exists without duplication."""
    res1 = seed_db(reset=False)
    user_count_1 = db_session.query(User).filter(User.email == "demo-merchant@apex.test").count()
    assert user_count_1 == 1, "Expected exactly 1 demo merchant user in database"

    user = db_session.query(User).filter(User.email == "demo-merchant@apex.test").first()
    assert user is not None
    assert user.role == "merchant_admin"
    assert user.is_active is True
    assert verify_password("ApexDemo@2026", user.hashed_password) is True

    # Re-run seeder a second time
    res2 = seed_db(reset=False)
    user_count_2 = db_session.query(User).filter(User.email == "demo-merchant@apex.test").count()
    assert user_count_2 == 1, "Expected 0 duplicate users after re-seeding"

def test_demo_merchant_login_success():
    """Requirement 8A & 8B: Demo merchant login succeeds and returns merchant_admin role."""
    response = client.post("/api/v1/auth/login-json", json={
        "email": "demo-merchant@apex.test",
        "password": "ApexDemo@2026"
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    assert "access_token" in data
    assert data["role"] == "merchant_admin"
    assert data["user"]["role"] == "merchant_admin"
    assert data["user"]["email"] == "demo-merchant@apex.test"

def test_demo_merchant_wrong_password_fails():
    """Requirement 8C: Wrong password fails with HTTP 401."""
    response = client.post("/api/v1/auth/login-json", json={
        "email": "demo-merchant@apex.test",
        "password": "WrongPassword123!"
    })
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]

def test_customer_cannot_access_merchant_apis(db_session: Session):
    """Requirement 8D: Customer accounts receive HTTP 403 when accessing merchant APIs."""
    customer = db_session.query(User).filter(User.role == "customer").first()
    if not customer:
        customer = User(
            email="test_cust_auth@apex.test",
            hashed_password=get_password_hash("password123"),
            full_name="Test Customer",
            role="customer",
            is_active=True
        )
        db_session.add(customer)
        db_session.commit()

    cust_token = create_access_token(subject=customer.id, merchant_id=customer.merchant_id, role="customer")
    headers = {"Authorization": f"Bearer {cust_token}"}

    # Protected Merchant endpoints
    endpoints = [
        ("/api/v1/approvals", "GET"),
        ("/api/v1/policies", "GET"),
        ("/api/v1/revenue/opportunities", "GET"),
        ("/api/v1/auth/merchant-profile", "GET")
    ]
    for path, method in endpoints:
        if method == "GET":
            resp = client.get(path, headers=headers)
        assert resp.status_code == 403, f"Expected 403 for customer accessing {path}, got {resp.status_code}"

def test_localstorage_tampering_defense(db_session: Session):
    """Requirement 8E: Modifying client-side claims cannot grant merchant privileges without valid server JWT."""
    customer = db_session.query(User).filter(User.role == "customer").first()
    cust_token = create_access_token(subject=customer.id, merchant_id=customer.merchant_id, role="customer")
    headers = {"Authorization": f"Bearer {cust_token}"}

    # Accessing merchant-only endpoint with customer JWT
    resp = client.get("/api/v1/auth/merchant-profile", headers=headers)
    assert resp.status_code == 403

def test_plaintext_password_never_exposed(db_session: Session):
    """Requirement 8G: Plaintext password is never exposed in profile or login responses."""
    resp = client.post("/api/v1/auth/login-json", json={
        "email": "demo-merchant@apex.test",
        "password": "ApexDemo@2026"
    })
    assert resp.status_code == 200
    res_str = resp.text
    assert "ApexDemo@2026" not in res_str
    assert "hashed_password" not in res_str

    token = resp.json()["access_token"]
    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    assert "ApexDemo@2026" not in me_resp.text
    assert "hashed_password" not in me_resp.text
