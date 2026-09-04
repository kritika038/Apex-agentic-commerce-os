import pytest
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.policy import Policy
from app.database.models.approval_request import ApprovalRequest
from app.database.models.transaction_authorization import TransactionAuthorization
from app.services.purchase_intent_service import PurchaseIntentService
from app.policies.policy_engine import PolicyEngine
from app.services.approval_service import ApprovalService
from app.tools.shopping_tools import add_to_cart

def test_human_approval_success_creates_authorization(client: TestClient, db: Session, setup_test_data, auth_headers):
    m1_id = setup_test_data["m1"]
    headers = auth_headers("u1@m1.com")

    # Policy requires approval above 5000
    policy = Policy(merchant_id=m1_id, version=1, max_transaction_amount=Decimal("10000.00"), approval_threshold=Decimal("5000.00"), is_active=True)
    db.add(policy)

    p_watch = Product(merchant_id=m1_id, name="Fitness Watch", price=Decimal("8500.00"), category="Electronics", is_active=True)
    db.add(p_watch)
    db.flush()
    db.add(Inventory(merchant_id=m1_id, product_id=p_watch.id, stock_quantity=10))
    db.commit()

    session_id = "sess_appr_flow"
    add_to_cart(db=db, merchant_id=m1_id, session_id=session_id, product_id=p_watch.id, quantity=1)

    intent = PurchaseIntentService.create_purchase_intent(
        db=db, merchant_id=m1_id, session_id=session_id, buyer_id="buyer_appr"
    )

    eval_res = PolicyEngine.evaluate_purchase_intent(db=db, purchase_intent_id=intent.id, merchant_id=m1_id)
    appr_id = eval_res["approval_request"]["id"]

    # 1. Approve request via API
    res_approve = client.post(f"/api/v1/approvals/{appr_id}/approve", json={"reason": "Verified with manager"}, headers=headers)
    assert res_approve.status_code == 200
    data = res_approve.json()
    assert data["approval"]["status"] == "APPROVED"
    assert data["authorization"]["status"] == "AUTHORIZED"
    assert Decimal(str(data["authorization"]["authorized_amount"])) == Decimal("8500.00")

    # 2. Verify authorization record in database
    auth_db = db.query(TransactionAuthorization).filter(TransactionAuthorization.id == data["authorization"]["id"]).first()
    assert auth_db is not None
    assert auth_db.status == "AUTHORIZED"
    assert Decimal(str(auth_db.authorized_amount)) == Decimal("8500.00")

def test_human_approval_rejection(client: TestClient, db: Session, setup_test_data, auth_headers):
    m1_id = setup_test_data["m1"]
    headers = auth_headers("u1@m1.com")

    policy = Policy(merchant_id=m1_id, version=1, max_transaction_amount=Decimal("10000.00"), approval_threshold=Decimal("5000.00"), is_active=True)
    db.add(policy)
    p_watch = Product(merchant_id=m1_id, name="Fitness Watch", price=Decimal("8500.00"), category="Electronics", is_active=True)
    db.add(p_watch)
    db.flush()
    db.add(Inventory(merchant_id=m1_id, product_id=p_watch.id, stock_quantity=10))
    db.commit()

    session_id = "sess_reject_flow"
    add_to_cart(db=db, merchant_id=m1_id, session_id=session_id, product_id=p_watch.id, quantity=1)
    intent = PurchaseIntentService.create_purchase_intent(db=db, merchant_id=m1_id, session_id=session_id, buyer_id="buyer_rej")
    eval_res = PolicyEngine.evaluate_purchase_intent(db=db, purchase_intent_id=intent.id, merchant_id=m1_id)
    appr_id = eval_res["approval_request"]["id"]

    # Reject request via API
    res_rej = client.post(f"/api/v1/approvals/{appr_id}/reject", json={"reason": "Customer flag"}, headers=headers)
    assert res_rej.status_code == 200
    assert res_rej.json()["approval"]["status"] == "REJECTED"

def test_atomic_approval_prevents_duplicate_or_conflict(client: TestClient, db: Session, setup_test_data, auth_headers):
    """
    Race Safety: Second approval attempt on already approved request returns 409 Conflict.
    """
    m1_id = setup_test_data["m1"]
    headers = auth_headers("u1@m1.com")

    policy = Policy(merchant_id=m1_id, version=1, max_transaction_amount=Decimal("10000.00"), approval_threshold=Decimal("5000.00"), is_active=True)
    db.add(policy)
    p_watch = Product(merchant_id=m1_id, name="Fitness Watch", price=Decimal("8500.00"), category="Electronics", is_active=True)
    db.add(p_watch)
    db.flush()
    db.add(Inventory(merchant_id=m1_id, product_id=p_watch.id, stock_quantity=10))
    db.commit()

    session_id = "sess_conflict_flow"
    add_to_cart(db=db, merchant_id=m1_id, session_id=session_id, product_id=p_watch.id, quantity=1)
    intent = PurchaseIntentService.create_purchase_intent(db=db, merchant_id=m1_id, session_id=session_id, buyer_id="buyer_conf")
    eval_res = PolicyEngine.evaluate_purchase_intent(db=db, purchase_intent_id=intent.id, merchant_id=m1_id)
    appr_id = eval_res["approval_request"]["id"]

    # 1. First approval succeeds
    res1 = client.post(f"/api/v1/approvals/{appr_id}/approve", headers=headers)
    assert res1.status_code == 200

    # 2. Second approval fails with 409 Conflict
    res2 = client.post(f"/api/v1/approvals/{appr_id}/approve", headers=headers)
    assert res2.status_code == 409
    assert "already in 'APPROVED' state" in res2.json()["detail"]

def test_expired_approval_cannot_be_approved(client: TestClient, db: Session, setup_test_data, auth_headers):
    """
    Expired approval requests cannot be approved.
    """
    m1_id = setup_test_data["m1"]
    headers = auth_headers("u1@m1.com")

    policy = Policy(merchant_id=m1_id, version=1, max_transaction_amount=Decimal("10000.00"), approval_threshold=Decimal("5000.00"), is_active=True)
    db.add(policy)
    p_watch = Product(merchant_id=m1_id, name="Fitness Watch", price=Decimal("8500.00"), category="Electronics", is_active=True)
    db.add(p_watch)
    db.flush()
    db.add(Inventory(merchant_id=m1_id, product_id=p_watch.id, stock_quantity=10))
    db.commit()

    session_id = "sess_exp_appr"
    add_to_cart(db=db, merchant_id=m1_id, session_id=session_id, product_id=p_watch.id, quantity=1)
    intent = PurchaseIntentService.create_purchase_intent(db=db, merchant_id=m1_id, session_id=session_id, buyer_id="buyer_exp")
    eval_res = PolicyEngine.evaluate_purchase_intent(db=db, purchase_intent_id=intent.id, merchant_id=m1_id)
    appr_id = eval_res["approval_request"]["id"]

    # Manually expire approval request in DB
    appr_db = db.query(ApprovalRequest).filter(ApprovalRequest.id == appr_id).first()
    appr_db.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=10)
    db.commit()

    # Attempt approval
    res = client.post(f"/api/v1/approvals/{appr_id}/approve", headers=headers)
    assert res.status_code == 400
    assert "has expired" in res.json()["detail"]

def test_cross_merchant_approval_isolation(client: TestClient, db: Session, setup_test_data, auth_headers):
    """
    User from Merchant 2 cannot approve or view approval from Merchant 1.
    """
    m1_id = setup_test_data["m1"]
    m2_headers = auth_headers("u2@m2.com")

    policy = Policy(merchant_id=m1_id, version=1, max_transaction_amount=Decimal("10000.00"), approval_threshold=Decimal("5000.00"), is_active=True)
    db.add(policy)
    p_watch = Product(merchant_id=m1_id, name="Fitness Watch", price=Decimal("8500.00"), category="Electronics", is_active=True)
    db.add(p_watch)
    db.flush()
    db.add(Inventory(merchant_id=m1_id, product_id=p_watch.id, stock_quantity=10))
    db.commit()

    session_id = "sess_iso_appr"
    add_to_cart(db=db, merchant_id=m1_id, session_id=session_id, product_id=p_watch.id, quantity=1)
    intent = PurchaseIntentService.create_purchase_intent(db=db, merchant_id=m1_id, session_id=session_id, buyer_id="buyer_iso")
    eval_res = PolicyEngine.evaluate_purchase_intent(db=db, purchase_intent_id=intent.id, merchant_id=m1_id)
    appr_id = eval_res["approval_request"]["id"]

    # Merchant 2 attempts to approve Merchant 1's request
    res = client.post(f"/api/v1/approvals/{appr_id}/approve", headers=m2_headers)
    assert res.status_code == 404
