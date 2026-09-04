import pytest
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.policy import Policy
from app.database.models.purchase_intent import PurchaseIntent
from app.policies.policy_engine import PolicyEngine
from app.services.purchase_intent_service import PurchaseIntentService
from app.tools.shopping_tools import add_to_cart

def test_policy_engine_allow_low_risk(db: Session, setup_test_data):
    """
    Path A: Low-risk transaction (₹3,898 <= ₹5,000 approval threshold).
    Result: ALLOW, TransactionAuthorization created.
    """
    m1_id = setup_test_data["m1"]
    
    # Policy: max 10k, approval 5k
    policy = Policy(
        merchant_id=m1_id,
        name="Test Policy",
        version=1,
        max_transaction_amount=Decimal("10000.00"),
        approval_threshold=Decimal("5000.00"),
        low_risk_limit=Decimal("2000.00"),
        max_discount_percent=Decimal("5.00"),
        max_quantity=5,
        allowed_currency="INR",
        auto_approval_enabled=True,
        authorization_expiration_minutes=10,
        is_active=True
    )
    db.add(policy)

    p1 = Product(merchant_id=m1_id, name="Pro Shoes", price=Decimal("3499.00"), category="Running", is_active=True)
    p2 = Product(merchant_id=m1_id, name="Socks", price=Decimal("399.00"), category="Accessories", is_active=True)
    db.add_all([p1, p2])
    db.flush()
    db.add(Inventory(merchant_id=m1_id, product_id=p1.id, stock_quantity=10))
    db.add(Inventory(merchant_id=m1_id, product_id=p2.id, stock_quantity=10))
    db.commit()

    session_id = "sess_policy_allow"
    add_to_cart(db=db, merchant_id=m1_id, session_id=session_id, product_id=p1.id, quantity=1)
    add_to_cart(db=db, merchant_id=m1_id, session_id=session_id, product_id=p2.id, quantity=1)

    intent = PurchaseIntentService.create_purchase_intent(
        db=db, merchant_id=m1_id, session_id=session_id, buyer_id="buyer_path_a"
    )

    eval_result = PolicyEngine.evaluate_purchase_intent(
        db=db, purchase_intent_id=intent.id, merchant_id=m1_id
    )

    assert eval_result["decision"] == "ALLOW"
    assert eval_result["requires_human_approval"] is False
    assert len(eval_result["violations"]) == 0
    assert eval_result["authorization"] is not None
    assert eval_result["authorization"]["status"] == "AUTHORIZED"
    assert Decimal(str(eval_result["authorization"]["authorized_amount"])) == Decimal("3898.00")

def test_policy_engine_requires_approval_high_risk(db: Session, setup_test_data):
    """
    Path B: High-risk transaction (₹8,500 > ₹5,000 approval threshold).
    Result: REQUIRES_APPROVAL, ApprovalRequest created.
    """
    m1_id = setup_test_data["m1"]
    
    policy = Policy(
        merchant_id=m1_id,
        name="Test Policy",
        version=1,
        max_transaction_amount=Decimal("10000.00"),
        approval_threshold=Decimal("5000.00"),
        low_risk_limit=Decimal("2000.00"),
        max_quantity=5,
        allowed_currency="INR",
        auto_approval_enabled=True,
        is_active=True
    )
    db.add(policy)

    p_watch = Product(merchant_id=m1_id, name="Fitness Watch", price=Decimal("8500.00"), category="Electronics", is_active=True)
    db.add(p_watch)
    db.flush()
    db.add(Inventory(merchant_id=m1_id, product_id=p_watch.id, stock_quantity=10))
    db.commit()

    session_id = "sess_policy_approval"
    add_to_cart(db=db, merchant_id=m1_id, session_id=session_id, product_id=p_watch.id, quantity=1)

    intent = PurchaseIntentService.create_purchase_intent(
        db=db, merchant_id=m1_id, session_id=session_id, buyer_id="buyer_path_b"
    )

    eval_result = PolicyEngine.evaluate_purchase_intent(
        db=db, purchase_intent_id=intent.id, merchant_id=m1_id
    )

    assert eval_result["decision"] == "REQUIRES_APPROVAL"
    assert eval_result["risk_level"] == "HIGH"
    assert eval_result["requires_human_approval"] is True
    assert eval_result["approval_request"] is not None
    assert eval_result["approval_request"]["status"] == "PENDING"
    assert Decimal(str(eval_result["approval_request"]["amount"])) == Decimal("8500.00")

def test_policy_engine_deny_exceeds_max_transaction(db: Session, setup_test_data):
    """
    Transaction (₹12,000) exceeds maximum transaction limit (₹10,000).
    Result: DENY.
    """
    m1_id = setup_test_data["m1"]
    
    policy = Policy(
        merchant_id=m1_id,
        name="Test Policy",
        version=1,
        max_transaction_amount=Decimal("10000.00"),
        approval_threshold=Decimal("5000.00"),
        low_risk_limit=Decimal("2000.00"),
        max_quantity=5,
        allowed_currency="INR",
        is_active=True
    )
    db.add(policy)

    p_expensive = Product(merchant_id=m1_id, name="Premium GPS Pro", price=Decimal("12000.00"), category="Electronics", is_active=True)
    db.add(p_expensive)
    db.flush()
    db.add(Inventory(merchant_id=m1_id, product_id=p_expensive.id, stock_quantity=10))
    db.commit()

    session_id = "sess_policy_deny_amt"
    add_to_cart(db=db, merchant_id=m1_id, session_id=session_id, product_id=p_expensive.id, quantity=1)

    intent = PurchaseIntentService.create_purchase_intent(
        db=db, merchant_id=m1_id, session_id=session_id, buyer_id="buyer_deny_amt"
    )

    eval_result = PolicyEngine.evaluate_purchase_intent(
        db=db, purchase_intent_id=intent.id, merchant_id=m1_id
    )

    assert eval_result["decision"] == "DENY"
    assert eval_result["risk_level"] == "HIGH"
    assert any("exceeds maximum transaction limit" in v for v in eval_result["violations"])

def test_policy_engine_deny_quantity_exceeded(db: Session, setup_test_data):
    """
    Total quantity (6) exceeds max_quantity (5).
    Result: DENY.
    """
    m1_id = setup_test_data["m1"]
    
    policy = Policy(
        merchant_id=m1_id,
        version=1,
        max_transaction_amount=Decimal("20000.00"),
        approval_threshold=Decimal("15000.00"),
        max_quantity=5,
        allowed_currency="INR",
        is_active=True
    )
    db.add(policy)

    p = Product(merchant_id=m1_id, name="Bulk Socks", price=Decimal("100.00"), category="Accessories", is_active=True)
    db.add(p)
    db.flush()
    db.add(Inventory(merchant_id=m1_id, product_id=p.id, stock_quantity=50))
    db.commit()

    session_id = "sess_qty_deny"
    add_to_cart(db=db, merchant_id=m1_id, session_id=session_id, product_id=p.id, quantity=6)

    intent = PurchaseIntentService.create_purchase_intent(
        db=db, merchant_id=m1_id, session_id=session_id, buyer_id="buyer_bulk"
    )

    eval_result = PolicyEngine.evaluate_purchase_intent(
        db=db, purchase_intent_id=intent.id, merchant_id=m1_id
    )

    assert eval_result["decision"] == "DENY"
    assert any("exceeds maximum allowed quantity" in v for v in eval_result["violations"])

def test_policy_engine_idempotent_evaluation(db: Session, setup_test_data):
    """
    Evaluating an already authorized intent returns the existing authorization idempotently.
    """
    m1_id = setup_test_data["m1"]
    policy = Policy(merchant_id=m1_id, version=1, max_transaction_amount=Decimal("10000.00"), approval_threshold=Decimal("5000.00"), is_active=True)
    db.add(policy)

    p = Product(merchant_id=m1_id, name="Shoes", price=Decimal("3499.00"), category="Running", is_active=True)
    db.add(p)
    db.flush()
    db.add(Inventory(merchant_id=m1_id, product_id=p.id, stock_quantity=10))
    db.commit()

    session_id = "sess_idempotent"
    add_to_cart(db=db, merchant_id=m1_id, session_id=session_id, product_id=p.id, quantity=1)

    intent = PurchaseIntentService.create_purchase_intent(
        db=db, merchant_id=m1_id, session_id=session_id, buyer_id="buyer_idem"
    )

    eval_1 = PolicyEngine.evaluate_purchase_intent(db=db, purchase_intent_id=intent.id, merchant_id=m1_id)
    auth_id_1 = eval_1["authorization"]["id"]

    eval_2 = PolicyEngine.evaluate_purchase_intent(db=db, purchase_intent_id=intent.id, merchant_id=m1_id)
    auth_id_2 = eval_2["authorization"]["id"]

    assert auth_id_1 == auth_id_2
