import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.core.config import settings
from app.database.models.inventory import Inventory
from app.database.models.product import Product
from app.database.models.payment_transaction import PaymentTransaction
from app.payments.simulator import PaymentSimulator
from app.payments.razorpay_provider import RazorpayProvider
from app.payments.state_machine import PaymentState

def _ensure_products(db: Session, merchant_id: str):
    p1 = db.query(Product).filter(Product.merchant_id == merchant_id, Product.name == "Pro Running Shoes").first()
    if not p1:
        p1 = Product(merchant_id=merchant_id, name="Pro Running Shoes", price=Decimal("3499.00"), category="Running", is_active=True)
        p2 = Product(merchant_id=merchant_id, name="Performance Socks", price=Decimal("399.00"), category="Accessories", is_active=True)
        db.add_all([p1, p2])
        db.flush()
        db.add(Inventory(merchant_id=merchant_id, product_id=p1.id, stock_quantity=20))
        db.add(Inventory(merchant_id=merchant_id, product_id=p2.id, stock_quantity=100))
        db.commit()
    return p1

def test_failure_simulator_timeout_scenario(client: TestClient, db: Session, setup_test_data):
    """
    Simulator Test: Triggers TIMEOUT scenario through the API endpoint.
    Verifies that PaymentTransaction status becomes UNKNOWN via actual provider simulation.
    """
    m1_id = setup_test_data["m1"]
    session_id = "sess_sim_to"

    p1 = _ensure_products(db, m1_id)
    client.post("/api/v1/ai/shopping", json={"session_id": session_id, "merchant_id": m1_id, "message": f"add product {p1.id} to cart"})
    
    res_pi = client.post("/api/v1/ai/purchase-intents", json={
        "session_id": session_id,
        "buyer_id": "buyer_sim_to",
        "merchant_id": m1_id,
        "constraints": {"max_price": 5000.0, "currency": "INR"}
    })
    pi_id = res_pi.json()["id"]
    res_eval = client.post(f"/api/v1/purchase-intents/{pi_id}/evaluate?merchant_id={m1_id}")
    auth_id = res_eval.json()["authorization"]["id"]

    res_sim = client.post(f"/api/v1/payments/simulator/scenario?merchant_id={m1_id}", json={
        "scenario": "TIMEOUT",
        "purchase_intent_id": pi_id,
        "authorization_id": auth_id
    })
    assert res_sim.status_code == 200
    sim_data = res_sim.json()
    assert sim_data["scenario"] == "TIMEOUT"
    assert sim_data["status"] == PaymentState.UNKNOWN
    assert sim_data["failure_code"] == "GATEWAY_TIMEOUT"

def test_failure_simulator_allowed_in_dev_test_demo(client: TestClient, setup_test_data, monkeypatch):
    """
    Security Test: Simulator endpoints are permitted when ENVIRONMENT is development, test, or demo.
    """
    m1_id = setup_test_data["m1"]

    for env_name in ["development", "test", "demo"]:
        monkeypatch.setattr(settings, "ENVIRONMENT", env_name)
        monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "mock")
        res = client.post(f"/api/v1/payments/simulator/scenario?merchant_id={m1_id}", json={
            "scenario": "SUCCESS"
        })
        assert res.status_code == 200

def test_failure_simulator_blocked_in_production(client: TestClient, setup_test_data, monkeypatch):
    """
    Security Test: Simulator endpoints must return 403 Forbidden when ENVIRONMENT is 'production'.
    """
    m1_id = setup_test_data["m1"]
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    res = client.post(f"/api/v1/payments/simulator/scenario?merchant_id={m1_id}", json={
        "scenario": "TIMEOUT"
    })
    assert res.status_code == 403
    assert "disabled in production" in res.json()["detail"].lower()

def test_failure_simulator_prohibits_razorpay_provider(client: TestClient, setup_test_data, monkeypatch):
    """
    Security Test: Simulator is strictly prohibited from using RazorpayProvider.
    """
    m1_id = setup_test_data["m1"]
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "razorpay")
    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", "rzp_test_mock123")
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", "mock_secret")

    res = client.post(f"/api/v1/payments/simulator/scenario?merchant_id={m1_id}", json={
        "scenario": "SUCCESS"
    })
    assert res.status_code == 403
    assert "prohibited from using razorpayprovider" in res.json()["detail"].lower()

def test_failure_simulator_never_mutates_state_directly(client: TestClient, db: Session, setup_test_data):
    """
    Architecture Invariant: The simulator executes provider interactions via MockPaymentProvider;
    it does not directly mutate transaction.status in the database.
    """
    m1_id = setup_test_data["m1"]
    p1 = _ensure_products(db, m1_id)
    session_id = "sess_sim_pipe"

    client.post("/api/v1/ai/shopping", json={"session_id": session_id, "merchant_id": m1_id, "message": f"add product {p1.id} to cart"})
    res_pi = client.post("/api/v1/ai/purchase-intents", json={
        "session_id": session_id, "buyer_id": "buyer_sim_pipe", "merchant_id": m1_id, "constraints": {"max_price": 5000.0, "currency": "INR"}
    })
    pi_id = res_pi.json()["id"]
    res_eval = client.post(f"/api/v1/purchase-intents/{pi_id}/evaluate?merchant_id={m1_id}")
    auth_id = res_eval.json()["authorization"]["id"]

    res_sim = client.post(f"/api/v1/payments/simulator/scenario?merchant_id={m1_id}", json={
        "scenario": "PROVIDER_4XX",
        "purchase_intent_id": pi_id,
        "authorization_id": auth_id
    })
    assert res_sim.status_code == 200
    tx_id = res_sim.json()["payment_transaction_id"]
    tx = db.query(PaymentTransaction).filter(PaymentTransaction.id == tx_id).first()
    assert tx.status == PaymentState.FAILED
    assert tx.failure_code == "INVALID_GATEWAY_REQUEST"
