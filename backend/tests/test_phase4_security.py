import pytest
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.policy import Policy
from app.database.models.transaction_authorization import TransactionAuthorization
from app.services.purchase_intent_service import PurchaseIntentService
from app.policies.policy_engine import PolicyEngine
from app.services.authorization_service import AuthorizationService
from app.tools.shopping_tools import add_to_cart

def test_authorization_amount_tamper_defense(db: Session, setup_test_data):
    """
    Test that TransactionAuthorization is strictly bound to the evaluated amount.
    Any attempt by downstream consumer to change amount to ₹1 fails verification.
    """
    m1_id = setup_test_data["m1"]
    policy = Policy(merchant_id=m1_id, version=1, max_transaction_amount=Decimal("10000.00"), approval_threshold=Decimal("5000.00"), is_active=True)
    db.add(policy)

    p = Product(merchant_id=m1_id, name="Shoes", price=Decimal("3499.00"), category="Running", is_active=True)
    db.add(p)
    db.flush()
    db.add(Inventory(merchant_id=m1_id, product_id=p.id, stock_quantity=10))
    db.commit()

    session_id = "sess_sec_auth"
    add_to_cart(db=db, merchant_id=m1_id, session_id=session_id, product_id=p.id, quantity=1)
    intent = PurchaseIntentService.create_purchase_intent(db=db, merchant_id=m1_id, session_id=session_id, buyer_id="buyer_sec")
    
    eval_res = PolicyEngine.evaluate_purchase_intent(db=db, purchase_intent_id=intent.id, merchant_id=m1_id)
    auth_id = eval_res["authorization"]["id"]

    # 1. Valid check with exact authorized amount
    valid, reason, _ = AuthorizationService.validate_authorization(
        db=db, authorization_id=auth_id, merchant_id=m1_id, expected_amount=Decimal("3499.00"), expected_currency="INR"
    )
    assert valid is True
    assert "valid and active" in reason

    # 2. Tampered check with ₹1.00 amount
    valid_tamper, reason_tamper, _ = AuthorizationService.validate_authorization(
        db=db, authorization_id=auth_id, merchant_id=m1_id, expected_amount=Decimal("1.00"), expected_currency="INR"
    )
    assert valid_tamper is False
    assert "Amount mismatch" in reason_tamper

def test_authorization_currency_tamper_defense(db: Session, setup_test_data):
    """
    Test that currency mismatch causes authorization validation failure.
    """
    m1_id = setup_test_data["m1"]
    policy = Policy(merchant_id=m1_id, version=1, max_transaction_amount=Decimal("10000.00"), approval_threshold=Decimal("5000.00"), is_active=True)
    db.add(policy)
    p = Product(merchant_id=m1_id, name="Shoes", price=Decimal("3499.00"), category="Running", is_active=True)
    db.add(p)
    db.flush()
    db.add(Inventory(merchant_id=m1_id, product_id=p.id, stock_quantity=10))
    db.commit()

    session_id = "sess_sec_curr"
    add_to_cart(db=db, merchant_id=m1_id, session_id=session_id, product_id=p.id, quantity=1)
    intent = PurchaseIntentService.create_purchase_intent(db=db, merchant_id=m1_id, session_id=session_id, buyer_id="buyer_curr")
    eval_res = PolicyEngine.evaluate_purchase_intent(db=db, purchase_intent_id=intent.id, merchant_id=m1_id)
    auth_id = eval_res["authorization"]["id"]

    valid, reason, _ = AuthorizationService.validate_authorization(
        db=db, authorization_id=auth_id, merchant_id=m1_id, expected_currency="USD"
    )
    assert valid is False
    assert "Currency mismatch" in reason

def test_expired_authorization_fails_validation(db: Session, setup_test_data):
    """
    Test that expired authorizations auto-expire and fail validation.
    """
    m1_id = setup_test_data["m1"]
    policy = Policy(merchant_id=m1_id, version=1, max_transaction_amount=Decimal("10000.00"), approval_threshold=Decimal("5000.00"), is_active=True)
    db.add(policy)
    p = Product(merchant_id=m1_id, name="Shoes", price=Decimal("3499.00"), category="Running", is_active=True)
    db.add(p)
    db.flush()
    db.add(Inventory(merchant_id=m1_id, product_id=p.id, stock_quantity=10))
    db.commit()

    session_id = "sess_sec_exp"
    add_to_cart(db=db, merchant_id=m1_id, session_id=session_id, product_id=p.id, quantity=1)
    intent = PurchaseIntentService.create_purchase_intent(db=db, merchant_id=m1_id, session_id=session_id, buyer_id="buyer_exp")
    eval_res = PolicyEngine.evaluate_purchase_intent(db=db, purchase_intent_id=intent.id, merchant_id=m1_id)
    auth_id = eval_res["authorization"]["id"]

    # Expire authorization in DB
    auth = db.query(TransactionAuthorization).filter(TransactionAuthorization.id == auth_id).first()
    auth.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=5)
    db.commit()

    valid, reason, updated_auth = AuthorizationService.validate_authorization(
        db=db, authorization_id=auth_id, merchant_id=m1_id
    )
    assert valid is False
    assert "expired" in reason
    assert updated_auth.status == "EXPIRED"

def test_no_payment_execution_in_phase_4(client: TestClient):
    """
    Ensure no direct charge or arbitrary payment execution endpoints exist.
    """
    res = client.post("/api/v1/payments/charge", json={})
    assert res.status_code in (404, 405)
    res2 = client.post("/api/v1/razorpay/orders", json={})
    assert res2.status_code in (404, 405)
