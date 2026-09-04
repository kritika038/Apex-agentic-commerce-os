"""
Regression test suite for Merchant Price Request Inbox Lifecycle, State Transitions,
Server-side Sorting, Expiration Safeguards, and Badge Counting.
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database.session import SessionLocal
from app.database.models.merchant import Merchant
from app.database.models.product import Product
from app.database.models.user import User
from app.database.models.negotiated_offer import NegotiatedOffer
from app.negotiation.state_machine import NegotiationState
from app.negotiation.engine import NegotiationEngine
from app.core.security import create_access_token
from scripts.seed import seed_db


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        seed_db(reset=False, db_session=db)
        yield db
    finally:
        db.close()


@pytest.fixture
def setup_test_data(db_session):
    merchant = db_session.query(Merchant).filter(Merchant.name == "Apex Sports Merchant").first()
    assert merchant is not None
    merchant_user = db_session.query(User).filter(User.email == "demo-merchant@apex.test").first()
    assert merchant_user is not None
    customer_user = db_session.query(User).filter(User.email == "customer@demo-sports.test").first()
    assert customer_user is not None
    product = db_session.query(Product).filter(Product.merchant_id == merchant.id, Product.is_active == True).first()
    assert product is not None

    return {
        "merchant": merchant,
        "merchant_user": merchant_user,
        "customer_user": customer_user,
        "product": product,
    }


def _auth_headers(merchant_user: User):
    token = create_access_token(
        subject=str(merchant_user.id),
        merchant_id=merchant_user.merchant_id,
        role=merchant_user.role
    )
    return {"Authorization": f"Bearer {token}"}


def test_merchant_inbox_sorting_and_filtering(db_session, setup_test_data):
    client = TestClient(app)
    merchant = setup_test_data["merchant"]
    merchant_user = setup_test_data["merchant_user"]
    customer_user = setup_test_data["customer_user"]
    product = setup_test_data["product"]
    now_utc = datetime.now(timezone.utc)

    # Clean existing offers for clean assertions
    db_session.query(NegotiatedOffer).filter(NegotiatedOffer.merchant_id == merchant.id).delete()
    db_session.commit()

    # 1. Pending offer (Needs human approval)
    pending_offer = NegotiatedOffer(
        tenant_id=merchant.id,
        negotiation_id="neg_pending_01",
        buyer_user_id=customer_user.email,
        merchant_id=merchant.id,
        product_id=product.id,
        quantity=1,
        list_price=Decimal("5000.00"),
        list_total=Decimal("5000.00"),
        requested_total=Decimal("4500.00"),
        final_total=Decimal("4500.00"),
        discount_amount=Decimal("500.00"),
        discount_percent=Decimal("10.00"),
        status=NegotiationState.HUMAN_APPROVAL_REQUIRED.value,
        expires_at=now_utc + timedelta(hours=2),
        created_at=now_utc - timedelta(minutes=10)
    )

    # 2. Counter-offered offer (Priority 1 in inbox)
    counter_offer = NegotiatedOffer(
        tenant_id=merchant.id,
        negotiation_id="neg_counter_01",
        buyer_user_id=customer_user.email,
        merchant_id=merchant.id,
        product_id=product.id,
        quantity=1,
        list_price=Decimal("5000.00"),
        list_total=Decimal("5000.00"),
        requested_total=Decimal("4000.00"),
        merchant_counter_total=Decimal("4600.00"),
        final_total=Decimal("4600.00"),
        discount_amount=Decimal("400.00"),
        discount_percent=Decimal("8.00"),
        status=NegotiationState.COUNTER_OFFERED.value,
        expires_at=now_utc + timedelta(hours=2),
        created_at=now_utc - timedelta(minutes=5)
    )

    # 3. Approved offer (Terminal / Inactive for pending view)
    approved_offer = NegotiatedOffer(
        tenant_id=merchant.id,
        negotiation_id="neg_approved_01",
        buyer_user_id=customer_user.email,
        merchant_id=merchant.id,
        product_id=product.id,
        quantity=1,
        list_price=Decimal("5000.00"),
        list_total=Decimal("5000.00"),
        requested_total=Decimal("4750.00"),
        final_total=Decimal("4750.00"),
        status=NegotiationState.AUTO_ACCEPTED.value,
        expires_at=now_utc + timedelta(hours=2),
        created_at=now_utc - timedelta(minutes=1)
    )

    # 4. Expired pending offer (Must not be counted in actionable badge or pending view)
    expired_pending_offer = NegotiatedOffer(
        tenant_id=merchant.id,
        negotiation_id="neg_expired_01",
        buyer_user_id=customer_user.email,
        merchant_id=merchant.id,
        product_id=product.id,
        quantity=1,
        list_price=Decimal("5000.00"),
        list_total=Decimal("5000.00"),
        requested_total=Decimal("4200.00"),
        final_total=Decimal("4200.00"),
        status=NegotiationState.HUMAN_APPROVAL_REQUIRED.value,
        expires_at=now_utc - timedelta(minutes=30),
        created_at=now_utc - timedelta(hours=1)
    )

    db_session.add_all([pending_offer, counter_offer, approved_offer, expired_pending_offer])
    db_session.commit()

    headers = _auth_headers(merchant_user)

    # 1. Badge count should count only non-expired pending offer (=1)
    resp_badge = client.get("/api/v1/negotiation/merchant-requests/badge", headers=headers)
    assert resp_badge.status_code == 200
    badge_data = resp_badge.json()
    assert badge_data["pending_count"] == 1
    assert badge_data["total_count"] == 4

    # 2. Default list sorting: Counter-offer first (Priority 1), then Pending (Priority 2), then others
    resp_list = client.get("/api/v1/negotiation/merchant-requests", headers=headers)
    assert resp_list.status_code == 200
    items = resp_list.json()
    assert len(items) == 4
    assert items[0]["id"] == counter_offer.id
    assert items[1]["id"] == pending_offer.id

    # 3. Pending filter: Excludes expired and approved
    resp_pending = client.get("/api/v1/negotiation/merchant-requests?status_filter=PENDING", headers=headers)
    assert resp_pending.status_code == 200
    pending_items = resp_pending.json()
    assert len(pending_items) == 1
    assert pending_items[0]["id"] == pending_offer.id


def test_merchant_actions_and_stale_error_handling(db_session, setup_test_data):
    client = TestClient(app)
    merchant = setup_test_data["merchant"]
    merchant_user = setup_test_data["merchant_user"]
    customer_user = setup_test_data["customer_user"]
    product = setup_test_data["product"]
    now_utc = datetime.now(timezone.utc)

    db_session.query(NegotiatedOffer).filter(NegotiatedOffer.merchant_id == merchant.id).delete()
    db_session.commit()

    offer_to_approve = NegotiatedOffer(
        tenant_id=merchant.id,
        negotiation_id="neg_act_01",
        buyer_user_id=customer_user.email,
        merchant_id=merchant.id,
        product_id=product.id,
        quantity=1,
        list_price=Decimal("5000.00"),
        list_total=Decimal("5000.00"),
        requested_total=Decimal("4500.00"),
        final_total=Decimal("4500.00"),
        discount_amount=Decimal("500.00"),
        discount_percent=Decimal("10.00"),
        status=NegotiationState.HUMAN_APPROVAL_REQUIRED.value,
        expires_at=now_utc + timedelta(hours=1),
        created_at=now_utc
    )

    expired_offer = NegotiatedOffer(
        tenant_id=merchant.id,
        negotiation_id="neg_act_expired",
        buyer_user_id=customer_user.email,
        merchant_id=merchant.id,
        product_id=product.id,
        quantity=1,
        list_price=Decimal("5000.00"),
        list_total=Decimal("5000.00"),
        requested_total=Decimal("4300.00"),
        final_total=Decimal("4300.00"),
        status=NegotiationState.HUMAN_APPROVAL_REQUIRED.value,
        expires_at=now_utc - timedelta(minutes=10),
        created_at=now_utc - timedelta(hours=1)
    )

    db_session.add_all([offer_to_approve, expired_offer])
    db_session.commit()

    headers = _auth_headers(merchant_user)

    # 1. Approve offer_to_approve
    resp_appr = client.post(
        f"/api/v1/negotiation/{offer_to_approve.id}/merchant/approve",
        json={"merchant_id": merchant.id, "reason": "Approved by admin"},
        headers=headers
    )
    assert resp_appr.status_code == 200
    appr_data = resp_appr.json()
    assert appr_data["status"] in [NegotiationState.AUTO_ACCEPTED.value, NegotiationState.MERCHANT_APPROVED.value]

    # Badge pending count should immediately reflect 0
    resp_badge = client.get("/api/v1/negotiation/merchant-requests/badge", headers=headers)
    assert resp_badge.json()["pending_count"] == 0

    # 2. Attempt to decline expired offer: must return clean 400
    resp_exp_decline = client.post(
        f"/api/v1/negotiation/{expired_offer.id}/merchant/reject",
        json={"merchant_id": merchant.id, "reason": "Decline expired"},
        headers=headers
    )
    assert resp_exp_decline.status_code == 400
    assert "expired" in resp_exp_decline.json()["detail"].lower()

    # 3. Attempt to counter expired offer: must return clean 400
    resp_exp_counter = client.post(
        f"/api/v1/negotiation/{expired_offer.id}/merchant/counter",
        json={"merchant_id": merchant.id, "counter_total": 4700.0, "reason": "Counter expired"},
        headers=headers
    )
    assert resp_exp_counter.status_code == 400
    assert "expired" in resp_exp_counter.json()["detail"].lower()

    # 4. Attempt to approve expired offer: must return clean 400
    resp_exp_approve = client.post(
        f"/api/v1/negotiation/{expired_offer.id}/merchant/approve",
        json={"merchant_id": merchant.id, "reason": "Approve expired"},
        headers=headers
    )
    assert resp_exp_approve.status_code == 400
    assert "expired" in resp_exp_approve.json()["detail"].lower()
