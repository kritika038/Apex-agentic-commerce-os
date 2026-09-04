import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database.session import get_db
from app.database.models.base import Base
from app.database.models.merchant import Merchant
from app.database.models.user import User
from app.core.security import get_password_hash

SQLALCHEMY_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)

from app.core.config import settings

@pytest.fixture(autouse=True)
def db_setup():
    orig_env = settings.ENVIRONMENT
    settings.ENVIRONMENT = "test"
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    settings.ENVIRONMENT = orig_env

@pytest.fixture
def db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    del app.dependency_overrides[get_db]

from decimal import Decimal
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.policy import Policy

@pytest.fixture
def setup_test_data(db):
    m1 = Merchant(name="M1", domain="m1.com")
    m2 = Merchant(name="M2", domain="m2.com")
    db.add(m1)
    db.add(m2)
    db.commit()

    u1 = User(email="u1@m1.com", hashed_password=get_password_hash("testpass"), merchant_id=m1.id, full_name="User 1")
    u2 = User(email="u2@m2.com", hashed_password=get_password_hash("testpass"), merchant_id=m2.id, full_name="User 2")
    u_no_merchant = User(email="u3@none.com", hashed_password=get_password_hash("testpass"), full_name="User 3")
    db.add_all([u1, u2, u_no_merchant])
    db.commit()

    return {"m1": m1.id, "m2": m2.id, "u1": u1, "u2": u2, "u3": u_no_merchant}

@pytest.fixture
def auth_headers(client, setup_test_data):
    def _get_headers(email="u1@m1.com"):
        res = client.post("/api/v1/auth/login", data={"username": email, "password": "testpass"})
        token = res.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    return _get_headers
