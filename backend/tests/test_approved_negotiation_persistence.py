"""
Regression test suite covering persistent approved negotiated offers.
Validates:
TEST A: Create negotiation -> merchant approval -> advance time beyond old TTL -> offer MUST remain MERCHANT_APPROVED.
TEST B: Merchant approves -> customer fetches My Price Requests after TTL -> MUST show MERCHANT_APPROVED.
TEST C: Merchant approves -> customer accepts after TTL -> MUST succeed.
TEST D: Merchant approves ₹4,127 -> checkout after TTL -> Razorpay order MUST use ₹4,127, not catalog price.
TEST E: Merchant approves -> inventory still available -> customer can purchase later.
TEST F: Merchant approves -> inventory becomes zero -> checkout blocked for stock, but offer is NOT converted to EXPIRED.
TEST G: Status / flags must not show pending/waiting for merchant review after MERCHANT_APPROVED.
TEST H: Status / flags must not show expired for MERCHANT_APPROVED.
TEST I: Unauthorized customer cannot use another customer's approved offer.
TEST J: Client-side price modification attempt is ignored; DB final_total remains authoritative.
"""

import uuid
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
from app.database.models.inventory import Inventory
from app.negotiation.state_machine import NegotiationState, NegotiationStateMachine, StateTransitionError
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


def _create_product(db: Session, merchant: Merchant, price: Decimal = Decimal("4299.00"), stock: int = 50) -> Product:
    prod_id = f"prod_test_{uuid.uuid4().hex[:10]}"
    product = Product(
        id=prod_id,
        merchant_id=merchant.id,
        name=f"Test Trail Running Shoe {uuid.uuid4().hex[:4]}",
        description="Premium running shoe for testing",
        category="Sports & Fitness",
        price=price,
        currency="INR",
        is_active=True
    )
    db.add(product)
    db.flush()
    inv = Inventory(
        merchant_id=merchant.id,
        product_id=product.id,
        stock_quantity=stock,
        reserved_quantity=0
    )
    db.add(inv)
    db.commit()
    db.refresh(product)
    return product


@pytest.fixture
def setup_test_data(db_session):
    merchant = db_session.query(Merchant).filter(Merchant.name == "Apex Sports Merchant").first()
    assert merchant is not None
    merchant_user = db_session.query(User).filter(User.email == "demo-merchant@apex.test").first()
    assert merchant_user is not None
    customer_user = db_session.query(User).filter(User.email == "customer@demo-sports.test").first()
    assert customer_user is not None
    other_customer = db_session.query(User).filter(User.email == "other-customer@test.com").first()
    if not other_customer:
        other_customer = User(
            email="other-customer@test.com",
            hashed_password="fakehashedpassword",
            full_name="Other Customer",
            role="customer",
            merchant_id=merchant.id,
            is_active=True
        )
        db_session.add(other_customer)
        db_session.commit()
        db_session.refresh(other_customer)

    return {
        "merchant": merchant,
        "merchant_user": merchant_user,
        "customer_user": customer_user,
        "other_customer": other_customer,
    }


def _auth_headers(user: User):
    token = create_access_token(
        subject=str(user.id),
        merchant_id=user.merchant_id,
        role=user.role
    )
    return {"Authorization": f"Bearer {token}"}


def offer_key_suffix():
    return uuid.uuid4().hex[:8]


def test_a_merchant_approval_remains_approved_after_ttl(db_session, setup_test_data):
    """TEST A: Create negotiation -> merchant approval -> advance time beyond old TTL -> offer MUST remain MERCHANT_APPROVED."""
    merchant = setup_test_data["merchant"]
    merchant_user = setup_test_data["merchant_user"]
    customer_user = setup_test_data["customer_user"]
    product = _create_product(db_session, merchant, price=Decimal("4299.00"))

    # Customer starts negotiation requesting discount that routes to merchant review
    list_price = Decimal(str(product.price))
    requested_price = Decimal("4127.00")
    offer, res = NegotiationEngine.evaluate_negotiation(
        db=db_session,
        merchant=merchant,
        product=product,
        quantity=1,
        requested_total=requested_price,
        buyer_user_id=customer_user.email,
        buyer_message="Student discount request",
        idempotency_key=f"idem_test_a_{offer_key_suffix()}"
    )

    assert offer.status == NegotiationState.HUMAN_APPROVAL_REQUIRED.value

    # Merchant approves
    approved_offer = NegotiationEngine.merchant_approve_offer(
        db=db_session,
        offer_id=offer.id,
        merchant_id=merchant.id,
        admin_user_id=merchant_user.id,
        reason="Approved student athlete discount."
    )
    assert approved_offer.status == NegotiationState.MERCHANT_APPROVED.value
    assert approved_offer.final_total == requested_price

    # Advance time 3 hours into the future (well beyond 15 min TTL)
    old_time = datetime.now(timezone.utc) - timedelta(hours=3)
    approved_offer.expires_at = old_time.replace(tzinfo=None)
    db_session.commit()
    db_session.refresh(approved_offer)

    # Invariant: Offer status remains MERCHANT_APPROVED and cannot transition to EXPIRED
    assert approved_offer.status == NegotiationState.MERCHANT_APPROVED.value
    assert approved_offer.is_actionable is True

    # State machine refuses transition to EXPIRED
    with pytest.raises(StateTransitionError):
        NegotiationStateMachine.validate_transition(approved_offer.status, NegotiationState.EXPIRED.value)


def test_b_customer_my_requests_shows_approved_after_ttl(db_session, setup_test_data):
    """TEST B: Merchant approves -> customer fetches My Price Requests after TTL -> MUST show MERCHANT_APPROVED."""
    client = TestClient(app)
    merchant = setup_test_data["merchant"]
    merchant_user = setup_test_data["merchant_user"]
    customer_user = setup_test_data["customer_user"]
    product = _create_product(db_session, merchant, price=Decimal("4299.00"))

    offer, _ = NegotiationEngine.evaluate_negotiation(
        db=db_session,
        merchant=merchant,
        product=product,
        quantity=1,
        requested_total=Decimal("4127.00"),
        buyer_user_id=customer_user.email,
        idempotency_key=f"idem_test_b_{offer_key_suffix()}"
    )

    NegotiationEngine.merchant_approve_offer(
        db=db_session,
        offer_id=offer.id,
        merchant_id=merchant.id,
        admin_user_id=merchant_user.id
    )

    # Expire original TTL timestamp
    offer.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2)
    db_session.commit()

    headers = _auth_headers(customer_user)
    # Fetch all
    res = client.get("/api/v1/negotiation/my-requests", headers=headers)
    assert res.status_code == 200
    offers = res.json()
    my_offer = next((o for o in offers if o["id"] == offer.id), None)
    assert my_offer is not None
    assert my_offer["status"] == NegotiationState.MERCHANT_APPROVED.value
    assert my_offer["is_actionable"] is True

    # Fetch actionable
    res_act = client.get("/api/v1/negotiation/my-requests?status_filter=ACTIONABLE", headers=headers)
    assert res_act.status_code == 200
    act_offers = res_act.json()
    assert any(o["id"] == offer.id for o in act_offers)

    # Fetch approved
    res_appr = client.get("/api/v1/negotiation/my-requests?status_filter=APPROVED", headers=headers)
    assert res_appr.status_code == 200
    appr_offers = res_appr.json()
    assert any(o["id"] == offer.id for o in appr_offers)


def test_c_customer_accepts_after_ttl(db_session, setup_test_data):
    """TEST C: Merchant approves -> customer accepts after TTL -> MUST succeed."""
    merchant = setup_test_data["merchant"]
    merchant_user = setup_test_data["merchant_user"]
    customer_user = setup_test_data["customer_user"]
    product = _create_product(db_session, merchant, price=Decimal("4299.00"))

    offer, _ = NegotiationEngine.evaluate_negotiation(
        db=db_session,
        merchant=merchant,
        product=product,
        quantity=1,
        requested_total=Decimal("4127.00"),
        buyer_user_id=customer_user.email,
        idempotency_key=f"idem_test_c_{offer_key_suffix()}"
    )

    NegotiationEngine.merchant_approve_offer(
        db=db_session,
        offer_id=offer.id,
        merchant_id=merchant.id,
        admin_user_id=merchant_user.id
    )

    # Simulate passing of 2 hours
    offer.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2)
    db_session.commit()

    # Customer accepts after TTL
    accepted = NegotiationEngine.customer_accept_offer(
        db=db_session,
        offer_id=offer.id,
        customer_id=customer_user.email,
        reason="I accept the approved price!"
    )
    assert accepted.status == NegotiationState.CUSTOMER_ACCEPTED.value


def test_d_checkout_after_ttl_uses_approved_price_not_catalog(db_session, setup_test_data):
    """TEST D: Merchant approves ₹4,127 -> checkout after TTL -> Razorpay order MUST use ₹4,127, not catalog price."""
    merchant = setup_test_data["merchant"]
    merchant_user = setup_test_data["merchant_user"]
    customer_user = setup_test_data["customer_user"]
    product = _create_product(db_session, merchant, price=Decimal("4299.00"))

    approved_amount = Decimal("4127.00")
    offer, _ = NegotiationEngine.evaluate_negotiation(
        db=db_session,
        merchant=merchant,
        product=product,
        quantity=1,
        requested_total=approved_amount,
        buyer_user_id=customer_user.email,
        idempotency_key=f"idem_test_d_{offer_key_suffix()}"
    )

    NegotiationEngine.merchant_approve_offer(
        db=db_session,
        offer_id=offer.id,
        merchant_id=merchant.id,
        admin_user_id=merchant_user.id
    )

    # Customer accepts
    NegotiationEngine.customer_accept_offer(
        db=db_session,
        offer_id=offer.id,
        customer_id=customer_user.email
    )

    # Simulate passing 4 hours
    offer.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=4)
    db_session.commit()

    # Change catalog price in DB to ensure checkout does not silently use catalog price
    product.price = Decimal("4999.00")
    db_session.commit()

    # Checkout
    order_res = NegotiationEngine.checkout_negotiated_offer(
        db=db_session,
        offer_id=offer.id,
        buyer_user_id=customer_user.email,
        merchant_id=merchant.id
    )

    assert order_res["status"] == "payment_ready"
    assert order_res["amount"] == 4127.00
    assert order_res["amount_paise"] == 412700


def test_e_inventory_available_customer_purchases_later(db_session, setup_test_data):
    """TEST E: Merchant approves -> inventory still available -> customer can purchase later."""
    merchant = setup_test_data["merchant"]
    merchant_user = setup_test_data["merchant_user"]
    customer_user = setup_test_data["customer_user"]
    product = _create_product(db_session, merchant, price=Decimal("4299.00"), stock=20)

    # 4127 * 2 = 8254 on 4299 * 2 = 8598 (4% discount)
    offer, _ = NegotiationEngine.evaluate_negotiation(
        db=db_session,
        merchant=merchant,
        product=product,
        quantity=2,
        requested_total=Decimal("8254.00"),
        buyer_user_id=customer_user.email,
        idempotency_key=f"idem_test_e_{offer_key_suffix()}"
    )

    NegotiationEngine.merchant_approve_offer(
        db=db_session,
        offer_id=offer.id,
        merchant_id=merchant.id,
        admin_user_id=merchant_user.id
    )

    # 1 day passes
    offer.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
    db_session.commit()

    order_res = NegotiationEngine.checkout_negotiated_offer(
        db=db_session,
        offer_id=offer.id,
        buyer_user_id=customer_user.email,
        merchant_id=merchant.id
    )
    assert order_res["amount"] == 8254.00


def test_f_inventory_zero_blocks_checkout_without_expiring_offer(db_session, setup_test_data):
    """TEST F: Merchant approves -> inventory becomes zero -> checkout blocked for stock, but offer is NOT converted to EXPIRED."""
    merchant = setup_test_data["merchant"]
    merchant_user = setup_test_data["merchant_user"]
    customer_user = setup_test_data["customer_user"]
    product = _create_product(db_session, merchant, price=Decimal("4299.00"), stock=10)

    offer, _ = NegotiationEngine.evaluate_negotiation(
        db=db_session,
        merchant=merchant,
        product=product,
        quantity=1,
        requested_total=Decimal("4127.00"),
        buyer_user_id=customer_user.email,
        idempotency_key=f"idem_test_f_{offer_key_suffix()}"
    )

    NegotiationEngine.merchant_approve_offer(
        db=db_session,
        offer_id=offer.id,
        merchant_id=merchant.id,
        admin_user_id=merchant_user.id
    )

    # Inventory goes to 0
    if product.inventory:
        product.inventory.stock_quantity = 0
    db_session.commit()

    # Checkout fails with out of stock error
    with pytest.raises(ValueError, match="out of stock|currently unavailable"):
        NegotiationEngine.checkout_negotiated_offer(
            db=db_session,
            offer_id=offer.id,
            buyer_user_id=customer_user.email,
            merchant_id=merchant.id
        )

    # Invariant: Offer remains MERCHANT_APPROVED, never corrupted to EXPIRED
    db_session.refresh(offer)
    assert offer.status == NegotiationState.MERCHANT_APPROVED.value


def test_g_and_h_pdp_validation_never_shows_waiting_or_expired(db_session, setup_test_data):
    """TEST G & H: Frontend validate-pdp must never show 'Waiting for merchant review' or 'Offer Expired' for approved offer."""
    client = TestClient(app)
    merchant = setup_test_data["merchant"]
    merchant_user = setup_test_data["merchant_user"]
    customer_user = setup_test_data["customer_user"]
    product = _create_product(db_session, merchant, price=Decimal("4299.00"))

    offer, _ = NegotiationEngine.evaluate_negotiation(
        db=db_session,
        merchant=merchant,
        product=product,
        quantity=1,
        requested_total=Decimal("4127.00"),
        buyer_user_id=customer_user.email,
        idempotency_key=f"idem_test_gh_{offer_key_suffix()}"
    )

    NegotiationEngine.merchant_approve_offer(
        db=db_session,
        offer_id=offer.id,
        merchant_id=merchant.id,
        admin_user_id=merchant_user.id
    )

    # Time past TTL
    offer.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=5)
    db_session.commit()

    headers = _auth_headers(customer_user)
    res = client.get(f"/api/v1/negotiation/{offer.id}/validate-pdp?product_id={product.id}", headers=headers)
    assert res.status_code == 200
    pdp_data = res.json()

    # Invariants for UI
    assert pdp_data["is_approved"] is True
    assert pdp_data["is_pending"] is False  # TEST G: Never waiting for merchant review
    assert pdp_data["is_expired"] is False  # TEST H: Never offer expired
    assert pdp_data["is_payable"] is True
    assert pdp_data["final_total"] == 4127.00


def test_i_unauthorized_customer_cannot_use_approved_offer(db_session, setup_test_data):
    """TEST I: Unauthorized customer cannot use another customer's approved offer."""
    merchant = setup_test_data["merchant"]
    merchant_user = setup_test_data["merchant_user"]
    customer_user = setup_test_data["customer_user"]
    other_customer = setup_test_data["other_customer"]
    product = _create_product(db_session, merchant, price=Decimal("4299.00"))

    offer, _ = NegotiationEngine.evaluate_negotiation(
        db=db_session,
        merchant=merchant,
        product=product,
        quantity=1,
        requested_total=Decimal("4127.00"),
        buyer_user_id=customer_user.email,
        idempotency_key=f"idem_test_i_{offer_key_suffix()}"
    )

    NegotiationEngine.merchant_approve_offer(
        db=db_session,
        offer_id=offer.id,
        merchant_id=merchant.id,
        admin_user_id=merchant_user.id
    )

    # Other customer attempts to accept
    with pytest.raises(ValueError, match="Customer mismatch"):
        NegotiationEngine.customer_accept_offer(
            db=db_session,
            offer_id=offer.id,
            customer_id=other_customer.email
        )

    # Other customer attempts to checkout
    with pytest.raises(ValueError, match="Customer mismatch"):
        NegotiationEngine.checkout_negotiated_offer(
            db=db_session,
            offer_id=offer.id,
            buyer_user_id=other_customer.email,
            merchant_id=merchant.id
        )


def test_j_client_side_price_tampering_ignored(db_session, setup_test_data):
    """TEST J: Client-side attempted price modification is ignored/rejected; DB NegotiatedOffer.final_total remains authoritative."""
    merchant = setup_test_data["merchant"]
    merchant_user = setup_test_data["merchant_user"]
    customer_user = setup_test_data["customer_user"]
    product = _create_product(db_session, merchant, price=Decimal("4299.00"))

    offer, _ = NegotiationEngine.evaluate_negotiation(
        db=db_session,
        merchant=merchant,
        product=product,
        quantity=1,
        requested_total=Decimal("4127.00"),
        buyer_user_id=customer_user.email,
        idempotency_key=f"idem_test_j_{offer_key_suffix()}"
    )

    NegotiationEngine.merchant_approve_offer(
        db=db_session,
        offer_id=offer.id,
        merchant_id=merchant.id,
        admin_user_id=merchant_user.id
    )

    # Client passes tampered amount ₹1.00
    with pytest.raises(ValueError, match="Price mismatch"):
        NegotiationEngine.checkout_negotiated_offer(
            db=db_session,
            offer_id=offer.id,
            buyer_user_id=customer_user.email,
            merchant_id=merchant.id,
            client_amount=Decimal("1.00")
        )

    # Normal checkout without client_amount strictly locks to DB ₹4,127.00
    order_res = NegotiationEngine.checkout_negotiated_offer(
        db=db_session,
        offer_id=offer.id,
        buyer_user_id=customer_user.email,
        merchant_id=merchant.id
    )
    assert order_res["amount"] == 4127.00



def offer_key_suffix():
    import uuid
    return uuid.uuid4().hex[:8]
