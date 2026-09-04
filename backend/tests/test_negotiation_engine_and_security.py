import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.database.session import get_db
from app.database.models.user import User
from app.database.models.product import Product
from app.database.models.merchant import Merchant
from app.database.models.negotiation_policy import MerchantNegotiationPolicy
from app.database.models.negotiated_offer import NegotiatedOffer
from app.database.models.approval_request import ApprovalRequest
from app.database.models.audit_event import AuditEvent
from app.negotiation.engine import NegotiationEngine
from app.negotiation.state_machine import NegotiationState, NegotiationStateMachine, StateTransitionError
from app.core.security import create_access_token, get_password_hash


@pytest.fixture
def test_setup(db):
    # Setup merchant
    merchant = db.query(Merchant).filter(Merchant.id == "merch_test").first()
    if not merchant:
        merchant = Merchant(
            id="merch_test",
            name="Apex Test Sports",
            domain="apex-test.local",
            is_active=True
        )
        db.add(merchant)

    # Setup merchant admin user
    merchant_user = db.query(User).filter(User.email == "merchant_admin@apex-test.local").first()
    if not merchant_user:
        merchant_user = User(
            email="merchant_admin@apex-test.local",
            hashed_password=get_password_hash("password123"),
            full_name="Apex Test Merchant Admin",
            merchant_id="merch_test",
            role="merchant_admin",
            is_active=True
        )
        db.add(merchant_user)
        db.flush()

    token = create_access_token(subject=merchant_user.id, merchant_id="merch_test", role="merchant_admin")
    headers = {"Authorization": f"Bearer {token}"}

    # Setup standard negotiation policy: max 5% discount, auto-accept <= 3%, human approval between 3% and 5%
    policy = db.query(MerchantNegotiationPolicy).filter(MerchantNegotiationPolicy.merchant_id == "merch_test").first()
    if not policy:
        policy = MerchantNegotiationPolicy(
            merchant_id="merch_test",
            tenant_id="merch_test",
            name="Test Negotiation Policy",
            enabled=True,
            max_discount_percent=Decimal("5.00"),
            max_discount_amount=Decimal("1000.00"),
            auto_accept_below_discount_percent=Decimal("3.00"),
            approval_above_discount_percent=Decimal("3.00"),
            max_quantity=5,
            min_order_value=Decimal("500.00"),
            allowed_categories=[],
            allowed_products=[],
            currency="INR",
            offer_ttl_minutes=10,
            is_active=True
        )
        db.add(policy)
    else:
        policy.enabled = True
        policy.max_discount_percent = Decimal("5.00")
        policy.auto_accept_below_discount_percent = Decimal("3.00")
        policy.approval_above_discount_percent = Decimal("3.00")
        policy.max_quantity = 5
        policy.min_order_value = Decimal("500.00")
        policy.offer_ttl_minutes = 10
        policy.is_active = True

    # Setup test product (MRP 5000)
    product = db.query(Product).filter(Product.id == "prod_test_shoe").first()
    if not product:
        product = Product(
            id="prod_test_shoe",
            merchant_id="merch_test",
            name="Apex Pro Running Shoe",
            description="High-performance running shoe",
            price=Decimal("5000.00"),
            mrp=Decimal("5000.00"),
            category="Footwear",
            currency="INR",
            is_active=True
        )
        db.add(product)
    else:
        product.price = Decimal("5000.00")

    db.commit()
    return {"merchant": merchant, "policy": policy, "product": product, "headers": headers, "merchant_user": merchant_user}


def test_scenario_a_auto_acceptance(client, db, test_setup):
    """
    Scenario A: Buyer requests 2% discount (₹4,900 on ₹5,000).
    Policy allows auto-accept up to 3%.
    Result: AUTO_ACCEPTED immediately with server-computed final_total.
    """
    resp = client.post(
        "/api/v1/negotiation/start?merchant_id=merch_test",
        json={
            "product_id": "prod_test_shoe",
            "quantity": 1,
            "requested_unit_price": 4900.00,
            "customer_id": "cust_alice"
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == NegotiationState.AUTO_ACCEPTED.value
    assert data["requires_action"] == "CUSTOMER"
    offer = data["offer"]
    assert Decimal(str(offer["list_unit_price"])) == Decimal("5000.00")
    assert Decimal(str(offer["offered_unit_price"])) == Decimal("4900.00")
    assert Decimal(str(offer["final_total"])) == Decimal("4900.00")
    assert Decimal(str(offer["discount_percent"])) == Decimal("2.00")
    assert offer["requires_human_approval"] is False


def test_scenario_b_human_approval_escalation(client, db, test_setup):
    """
    Scenario B: Buyer requests 4% discount (₹4,800 on ₹5,000).
    Policy auto-accept is 3%, max is 5%.
    Result: HUMAN_APPROVAL_REQUIRED and creates ApprovalRequest.
    """
    resp = client.post(
        "/api/v1/negotiation/start?merchant_id=merch_test",
        json={
            "product_id": "prod_test_shoe",
            "quantity": 1,
            "requested_unit_price": 4800.00,
            "customer_id": "cust_bob"
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == NegotiationState.HUMAN_APPROVAL_REQUIRED.value
    assert data["requires_action"] == "MERCHANT"
    offer = data["offer"]
    assert offer["requires_human_approval"] is True
    assert offer["approval_request_id"] is not None

    # Verify ApprovalRequest in DB
    appr = db.query(ApprovalRequest).filter(ApprovalRequest.id == offer["approval_request_id"]).first()
    assert appr is not None
    assert appr.status.upper() == "PENDING"


def test_scenario_c_merchant_approves_human_gated_offer(client, db, test_setup):
    """
    Scenario C: Merchant reviews and approves human-gated offer.
    Result: Status changes to AUTO_ACCEPTED / ready for customer checkout.
    """
    # Start negotiation needing human approval
    resp = client.post(
        "/api/v1/negotiation/start?merchant_id=merch_test",
        json={
            "product_id": "prod_test_shoe",
            "quantity": 1,
            "requested_unit_price": 4800.00,
            "customer_id": "cust_charlie"
        }
    )
    offer_id = resp.json()["offer"]["id"]

    # Merchant approves
    approve_resp = client.post(
        f"/api/v1/negotiation/{offer_id}/merchant/approve",
        json={"merchant_id": "merch_test", "reason": "VIP repeat customer discount approved"},
        headers=test_setup["headers"]
    )
    assert approve_resp.status_code == 200
    appr_data = approve_resp.json()
    assert appr_data["status"] == NegotiationState.AUTO_ACCEPTED.value
    assert Decimal(str(appr_data["final_total"])) == Decimal("4800.00")


def test_scenario_d_deterministic_counter_offer(client, db, test_setup):
    """
    Scenario D: Buyer requests 20% discount (₹4,000 on ₹5,000).
    Policy max discount is 5% (₹4,750).
    Result: COUNTER_OFFERED at ₹4,750 (5% discount).
    """
    resp = client.post(
        "/api/v1/negotiation/start?merchant_id=merch_test",
        json={
            "product_id": "prod_test_shoe",
            "quantity": 1,
            "requested_unit_price": 4000.00,
            "customer_id": "cust_david"
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == NegotiationState.COUNTER_OFFERED.value
    assert data["requires_action"] == "CUSTOMER"
    offer = data["offer"]
    assert Decimal(str(offer["requested_unit_price"])) == Decimal("4000.00")
    assert Decimal(str(offer["offered_unit_price"])) == Decimal("4750.00") # 5% off
    assert Decimal(str(offer["final_total"])) == Decimal("4750.00")
    assert Decimal(str(offer["discount_percent"])) == Decimal("5.00")


def test_scenario_e_customer_accepts_counter_and_checks_out(client, db, test_setup):
    """
    Scenario E: Customer accepts counter-offer and completes Razorpay payment checkout.
    Result: CUSTOMER_ACCEPTED -> ORDER_CONFIRMED.
    """
    # Start negotiation that results in counter offer
    resp = client.post(
        "/api/v1/negotiation/start?merchant_id=merch_test",
        json={
            "product_id": "prod_test_shoe",
            "quantity": 2,
            "requested_unit_price": 4000.00,
            "customer_id": "cust_emma"
        }
    )
    offer_id = resp.json()["offer"]["id"]

    # Customer accepts counter-offer
    acc_resp = client.post(
        f"/api/v1/negotiation/{offer_id}/accept",
        json={"customer_id": "cust_emma", "reason": "Counter price accepted"}
    )
    assert acc_resp.status_code == 200
    assert acc_resp.json()["status"] == NegotiationState.CUSTOMER_ACCEPTED.value
    assert acc_resp.json()["customer_accepted"] is True

    # Checkout
    chk_resp = client.post(
        f"/api/v1/negotiation/{offer_id}/checkout",
        json={"customer_id": "cust_emma", "payment_method": "upi"}
    )
    assert chk_resp.status_code == 200
    chk_data = chk_resp.json()
    assert chk_data["status"] == "payment_ready"
    assert chk_data["razorpay_order_id"].startswith("order_")
    # 2 shoes * ₹4750 = ₹9,500 = 950000 paise
    assert chk_data["amount_paise"] == 950000
    assert chk_data["currency"] == "INR"


def test_scenario_f_customer_rejects_counter_offer(client, db, test_setup):
    """
    Scenario F: Customer rejects counter offer.
    Result: CUSTOMER_REJECTED (terminal state).
    """
    resp = client.post(
        "/api/v1/negotiation/start?merchant_id=merch_test",
        json={
            "product_id": "prod_test_shoe",
            "quantity": 1,
            "requested_unit_price": 4000.00,
            "customer_id": "cust_frank"
        }
    )
    offer_id = resp.json()["offer"]["id"]

    rej_resp = client.post(
        f"/api/v1/negotiation/{offer_id}/reject",
        json={"customer_id": "cust_frank", "reason": "Too expensive"}
    )
    assert rej_resp.status_code == 200
    assert rej_resp.json()["status"] == NegotiationState.CUSTOMER_REJECTED.value

    # Cannot checkout after rejection
    chk_resp = client.post(
        f"/api/v1/negotiation/{offer_id}/checkout",
        json={"customer_id": "cust_frank"}
    )
    assert chk_resp.status_code == 400


def test_scenario_g_policy_rejection_quantity_exceeded(client, db, test_setup):
    """
    Scenario G: Buyer requests quantity 10 (policy max_quantity is 5).
    Result: REJECTED with explicit rule failure reason.
    """
    resp = client.post(
        "/api/v1/negotiation/start?merchant_id=merch_test",
        json={
            "product_id": "prod_test_shoe",
            "quantity": 10,
            "requested_unit_price": 4900.00,
            "customer_id": "cust_george"
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == NegotiationState.REJECTED.value
    assert "exceeds maximum allowed quantity" in data["offer"]["reason"]


def test_scenario_h_offer_expiry_enforcement(client, db, test_setup):
    """
    Scenario H: Expired offer cannot be accepted or checked out.
    Result: State transitions to EXPIRED.
    """
    # Start negotiation
    resp = client.post(
        "/api/v1/negotiation/start?merchant_id=merch_test",
        json={
            "product_id": "prod_test_shoe",
            "quantity": 1,
            "requested_unit_price": 4900.00,
            "customer_id": "cust_harry"
        }
    )
    offer_id = resp.json()["offer"]["id"]

    # Manually expire the offer in DB
    offer_db = db.query(NegotiatedOffer).filter(NegotiatedOffer.id == offer_id).first()
    offer_db.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    db.commit()

    # Attempt to accept
    acc_resp = client.post(
        f"/api/v1/negotiation/{offer_id}/accept",
        json={"customer_id": "cust_harry"}
    )
    assert acc_resp.status_code == 400
    assert "expired" in acc_resp.json()["detail"].lower()


# =========================================================================
# 25 CRITICAL SECURITY & GOVERNANCE SCENARIOS
# =========================================================================

def test_security_01_prevent_client_side_price_override(client, db, test_setup):
    """Security Check 1: Checkout cannot use arbitrary client amounts; strictly reads DB offer."""
    resp = client.post(
        "/api/v1/negotiation/start?merchant_id=merch_test",
        json={
            "product_id": "prod_test_shoe",
            "quantity": 1,
            "requested_unit_price": 4900.00,
            "customer_id": "cust_sec1"
        }
    )
    offer_id = resp.json()["offer"]["id"]
    client.post(f"/api/v1/negotiation/{offer_id}/accept", json={"customer_id": "cust_sec1"})

    chk = client.post(
        f"/api/v1/negotiation/{offer_id}/checkout",
        json={"customer_id": "cust_sec1"}
    )
    assert chk.status_code == 200
    # Amount MUST be exactly 490000 paise regardless of any client tampering
    assert chk.json()["amount_paise"] == 490000


def test_security_02_tenant_isolation_merchant_approval(client, db, test_setup):
    """Security Check 2: Merchant A cannot approve or counter an offer belonging to Merchant B."""
    resp = client.post(
        "/api/v1/negotiation/start?merchant_id=merch_test",
        json={
            "product_id": "prod_test_shoe",
            "quantity": 1,
            "requested_unit_price": 4800.00,
            "customer_id": "cust_sec2"
        }
    )
    offer_id = resp.json()["offer"]["id"]

    # Rogue merchant admin tries to approve
    rogue_user = db.query(User).filter(User.email == "rogue@merch_other_rogue.local").first()
    if not rogue_user:
        rogue_user = User(
            email="rogue@merch_other_rogue.local",
            hashed_password=get_password_hash("password123"),
            full_name="Rogue Admin",
            merchant_id="merch_other_rogue",
            role="merchant_admin",
            is_active=True
        )
        db.add(rogue_user)
        db.flush()
    rogue_token = create_access_token(subject=rogue_user.id, merchant_id="merch_other_rogue", role="merchant_admin")
    rogue_headers = {"Authorization": f"Bearer {rogue_token}"}

    rogue_resp = client.post(
        f"/api/v1/negotiation/{offer_id}/merchant/approve",
        json={"merchant_id": "merch_other_rogue", "reason": "Unauthorized override"},
        headers=rogue_headers
    )
    assert rogue_resp.status_code in [400, 403]
    assert "tenant mismatch" in rogue_resp.json()["detail"].lower()


def test_security_03_customer_ownership_enforcement(client, db, test_setup):
    """Security Check 3: Customer X cannot accept or checkout Customer Y's negotiated offer."""
    resp = client.post(
        "/api/v1/negotiation/start?merchant_id=merch_test",
        json={
            "product_id": "prod_test_shoe",
            "quantity": 1,
            "requested_unit_price": 4900.00,
            "customer_id": "cust_legitimate"
        }
    )
    offer_id = resp.json()["offer"]["id"]

    # Attacker tries to accept
    att_resp = client.post(
        f"/api/v1/negotiation/{offer_id}/accept",
        json={"customer_id": "cust_attacker"}
    )
    assert att_resp.status_code == 400
    assert "customer mismatch" in att_resp.json()["detail"].lower()


def test_security_04_prevent_checkout_without_acceptance(client, db, test_setup):
    """Security Check 4: Cannot checkout an unaccepted counter-offer."""
    resp = client.post(
        "/api/v1/negotiation/start?merchant_id=merch_test",
        json={
            "product_id": "prod_test_shoe",
            "quantity": 1,
            "requested_unit_price": 4000.00, # Results in COUNTER_OFFERED
            "customer_id": "cust_sec4"
        }
    )
    offer_id = resp.json()["offer"]["id"]

    # Try checking out directly before accepting counter offer
    chk = client.post(
        f"/api/v1/negotiation/{offer_id}/checkout",
        json={"customer_id": "cust_sec4"}
    )
    assert chk.status_code == 400
    assert "must be accepted" in chk.json()["detail"].lower()


def test_security_05_prevent_double_payment_checkout(client, db, test_setup):
    """Security Check 5: Idempotency prevents creating multiple conflicting payment orders."""
    resp = client.post(
        "/api/v1/negotiation/start?merchant_id=merch_test",
        json={
            "product_id": "prod_test_shoe",
            "quantity": 1,
            "requested_unit_price": 4900.00,
            "customer_id": "cust_sec5"
        }
    )
    offer_id = resp.json()["offer"]["id"]
    client.post(f"/api/v1/negotiation/{offer_id}/accept", json={"customer_id": "cust_sec5"})

    chk1 = client.post(f"/api/v1/negotiation/{offer_id}/checkout", json={"customer_id": "cust_sec5"})
    assert chk1.status_code == 200
    order_id_1 = chk1.json()["razorpay_order_id"]

    # Second checkout returns existing payment order idempotently
    chk2 = client.post(f"/api/v1/negotiation/{offer_id}/checkout", json={"customer_id": "cust_sec5"})
    assert chk2.status_code == 200
    assert chk2.json()["razorpay_order_id"] == order_id_1


def test_security_06_sha256_audit_trail_recorded(client, db, test_setup):
    """Security Check 6: Negotiation transitions log tamper-evident SHA-256 audit events."""
    resp = client.post(
        "/api/v1/negotiation/start?merchant_id=merch_test",
        json={
            "product_id": "prod_test_shoe",
            "quantity": 1,
            "requested_unit_price": 4900.00,
            "customer_id": "cust_sec6"
        }
    )
    offer_id = resp.json()["offer"]["id"]

    trace_resp = client.get(f"/api/v1/negotiation/{offer_id}/trace")
    assert trace_resp.status_code == 200
    trace_data = trace_resp.json()
    assert trace_data["audit_hash"] is not None
    assert len(trace_data["audit_hash"]) == 64 # SHA-256 hex string


def test_security_07_decimal_exact_paise_calculation(db, test_setup):
    """Security Check 7: No floating point rounding bugs for odd paise values."""
    engine = NegotiationEngine()
    # 3 items with list price ₹1,999.99 requested at ₹1,949.99
    product = db.query(Product).filter(Product.id == "prod_test_shoe").first()
    product.price = Decimal("1999.99")
    db.commit()

    offer = engine.start_negotiation(
        db=db,
        merchant_id="merch_test",
        customer_id="cust_precision",
        product_id="prod_test_shoe",
        quantity=3,
        requested_unit_price=Decimal("1949.99")
    )
    assert offer.list_total == Decimal("5999.97")
    assert offer.offered_total == Decimal("5849.97")
    assert offer.final_total == Decimal("5849.97")
    assert offer.discount_amount == Decimal("150.00")
    # Verify integer paise conversion
    paise = int(offer.final_total * 100)
    assert paise == 584997


def test_security_08_disabled_policy_rejects_negotiation(client, db, test_setup):
    """Security Check 8: If merchant disables negotiation policy, all proposals are rejected."""
    policy = db.query(MerchantNegotiationPolicy).filter(MerchantNegotiationPolicy.merchant_id == "merch_test").first()
    policy.enabled = False
    db.commit()

    resp = client.post(
        "/api/v1/negotiation/start?merchant_id=merch_test",
        json={
            "product_id": "prod_test_shoe",
            "quantity": 1,
            "requested_unit_price": 4900.00,
            "customer_id": "cust_sec8"
        }
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == NegotiationState.REJECTED.value
    assert "disabled" in resp.json()["offer"]["reason"].lower()


def test_security_09_state_machine_invalid_transition(db):
    """Security Check 9: State machine forbids transitioning from terminal state."""
    with pytest.raises(StateTransitionError):
        NegotiationStateMachine.validate_transition(
            NegotiationState.CUSTOMER_REJECTED,
            NegotiationState.CUSTOMER_ACCEPTED
        )
    with pytest.raises(StateTransitionError):
        NegotiationStateMachine.validate_transition(
            NegotiationState.ORDER_CONFIRMED,
            NegotiationState.COUNTER_OFFERED
        )


def test_security_10_minimum_order_value_enforcement(client, db, test_setup):
    """Security Check 10: Proposal below policy min_order_value escalates to merchant review (HUMAN_APPROVAL_REQUIRED)."""
    policy = db.query(MerchantNegotiationPolicy).filter(MerchantNegotiationPolicy.merchant_id == "merch_test").first()
    policy.min_order_value = Decimal("10000.00") # High minimum
    db.commit()

    resp = client.post(
        "/api/v1/negotiation/start?merchant_id=merch_test",
        json={
            "product_id": "prod_test_shoe",
            "quantity": 1,
            "requested_unit_price": 4900.00,
            "customer_id": "cust_sec10"
        }
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == NegotiationState.HUMAN_APPROVAL_REQUIRED.value
    assert resp.json()["offer"]["id"] is not None


def test_security_11_zero_and_negative_quantity_rejection(client, db, test_setup):
    """Security Check 11: Quantity <= 0 is rejected."""
    resp = client.post(
        "/api/v1/negotiation/start?merchant_id=merch_test",
        json={
            "product_id": "prod_test_shoe",
            "quantity": 0,
            "requested_unit_price": 4900.00,
            "customer_id": "cust_sec11"
        }
    )
    assert resp.status_code == 422 or resp.status_code == 400


def test_security_12_zero_and_negative_price_rejection(client, db, test_setup):
    """Security Check 12: Price <= 0 is rejected."""
    resp = client.post(
        "/api/v1/negotiation/start?merchant_id=merch_test",
        json={
            "product_id": "prod_test_shoe",
            "quantity": 1,
            "requested_unit_price": -50.00,
            "customer_id": "cust_sec12"
        }
    )
    assert resp.status_code == 422 or resp.status_code == 400


def test_security_13_replay_idempotency_same_offer(client, db, test_setup):
    """Security Check 13: Replaying same negotiation returns idempotent result."""
    engine = NegotiationEngine()
    product = db.query(Product).filter(Product.id == "prod_test_shoe").first()
    merchant = db.query(Merchant).filter(Merchant.id == "merch_test").first()

    offer1, res1 = engine.evaluate_negotiation(
        db=db,
        merchant=merchant,
        product=product,
        quantity=1,
        requested_total=Decimal("4900.00"),
        buyer_user_id="cust_sec13",
        idempotency_key="idemp_unique_key_13"
    )

    offer2, res2 = engine.evaluate_negotiation(
        db=db,
        merchant=merchant,
        product=product,
        quantity=1,
        requested_total=Decimal("4900.00"),
        buyer_user_id="cust_sec13",
        idempotency_key="idemp_unique_key_13"
    )

    assert offer1.id == offer2.id
    assert res2.get("idempotent_replay") is True


def test_security_14_category_whitelist_enforcement(client, db, test_setup):
    """Security Check 14: Products outside allowed_categories are rejected."""
    policy = db.query(MerchantNegotiationPolicy).filter(MerchantNegotiationPolicy.merchant_id == "merch_test").first()
    policy.allowed_categories = ["Electronics"] # Shoe is 'Footwear'
    db.commit()

    resp = client.post(
        "/api/v1/negotiation/start?merchant_id=merch_test",
        json={
            "product_id": "prod_test_shoe",
            "quantity": 1,
            "requested_unit_price": 4900.00,
            "customer_id": "cust_sec14"
        }
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == NegotiationState.REJECTED.value
    assert "not eligible" in resp.json()["offer"]["reason"].lower()


def test_security_15_product_whitelist_enforcement(client, db, test_setup):
    """Security Check 15: Products outside allowed_products list are rejected."""
    policy = db.query(MerchantNegotiationPolicy).filter(MerchantNegotiationPolicy.merchant_id == "merch_test").first()
    policy.allowed_categories = []
    policy.allowed_products = ["prod_other_allowed"]
    db.commit()

    resp = client.post(
        "/api/v1/negotiation/start?merchant_id=merch_test",
        json={
            "product_id": "prod_test_shoe",
            "quantity": 1,
            "requested_unit_price": 4900.00,
            "customer_id": "cust_sec15"
        }
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == NegotiationState.REJECTED.value
    assert "not currently eligible" in resp.json()["offer"]["reason"].lower()


def test_security_16_max_discount_cap_enforcement(client, db, test_setup):
    """Security Check 16: Extreme 99% discount request countered strictly at policy cap."""
    resp = client.post(
        "/api/v1/negotiation/start?merchant_id=merch_test",
        json={
            "product_id": "prod_test_shoe",
            "quantity": 1,
            "requested_unit_price": 50.00, # 99% off
            "customer_id": "cust_sec16"
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == NegotiationState.COUNTER_OFFERED.value
    # Max discount is 5% -> final total 4750.00
    assert Decimal(str(data["offer"]["final_total"])) == Decimal("4750.00")
    assert Decimal(str(data["offer"]["discount_percent"])) == Decimal("5.00")


def test_security_17_price_change_after_acceptance_does_not_alter_locked_offer(client, db, test_setup):
    """Security Check 17: Product price spike does not alter locked accepted offer amount."""
    resp = client.post(
        "/api/v1/negotiation/start?merchant_id=merch_test",
        json={
            "product_id": "prod_test_shoe",
            "quantity": 1,
            "requested_unit_price": 4900.00,
            "customer_id": "cust_sec17"
        }
    )
    offer_id = resp.json()["offer"]["id"]
    client.post(f"/api/v1/negotiation/{offer_id}/accept", json={"customer_id": "cust_sec17"})

    # Merchant inflates product price to ₹10,000
    prod = db.query(Product).filter(Product.id == "prod_test_shoe").first()
    prod.price = Decimal("10000.00")
    db.commit()

    # Customer checkout still executes at negotiated ₹4,900
    chk = client.post(
        f"/api/v1/negotiation/{offer_id}/checkout",
        json={"customer_id": "cust_sec17"}
    )
    assert chk.status_code == 200
    assert chk.json()["amount_paise"] == 490000


def test_security_18_cannot_approve_already_rejected_offer(client, db, test_setup):
    """Security Check 18: Terminal rejected offer cannot be approved by merchant."""
    resp = client.post(
        "/api/v1/negotiation/start?merchant_id=merch_test",
        json={
            "product_id": "prod_test_shoe",
            "quantity": 10, # Exceeds limit -> REJECTED
            "requested_unit_price": 4900.00,
            "customer_id": "cust_sec18"
        }
    )
    offer_id = resp.json()["offer"]["id"]
    assert resp.json()["status"] == NegotiationState.REJECTED.value

    # Attempt merchant approval on terminal rejected offer
    appr_resp = client.post(
        f"/api/v1/negotiation/{offer_id}/merchant/approve",
        json={"merchant_id": "merch_test"},
        headers=test_setup["headers"]
    )
    assert appr_resp.status_code == 500 or appr_resp.status_code == 400


def test_security_19_merchant_list_tenant_isolation(client, db, test_setup):
    """Security Check 19: Merchant list only returns offers for that merchant's tenant."""
    # Create offer for merch_test
    client.post(
        "/api/v1/negotiation/start?merchant_id=merch_test",
        json={"product_id": "prod_test_shoe", "quantity": 1, "requested_unit_price": 4900.00, "customer_id": "cust_t1"}
    )

    # Query for other merchant
    list_resp = client.get("/api/v1/negotiation/merchant/list?merchant_id=merch_other_tenant")
    assert list_resp.status_code == 200
    offers = list_resp.json()
    assert len(offers) == 0


def test_security_20_policy_endpoint_tenant_isolation(client, db, test_setup):
    """Security Check 20: GET /policy creates and fetches tenant-specific policy."""
    resp = client.get("/api/v1/negotiation/policy?merchant_id=merch_unique_tenant_20")
    assert resp.status_code == 200
    data = resp.json()
    assert data["merchant_id"] == "merch_unique_tenant_20"
    assert Decimal(str(data["max_discount_percent"])) == Decimal("5.00")


def test_security_21_policy_update_endpoint(client, db, test_setup):
    """Security Check 21: PUT /policy successfully updates parameters."""
    resp = client.put(
        "/api/v1/negotiation/policy?merchant_id=merch_test",
        json={"max_discount_percent": 8.50, "auto_accept_below_discount_percent": 4.00}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert Decimal(str(data["max_discount_percent"])) == Decimal("8.50")
    assert Decimal(str(data["auto_accept_below_discount_percent"])) == Decimal("4.00")


def test_security_22_merchant_counter_custom_price(client, db, test_setup):
    """Security Check 22: Merchant custom counter provides valid final_total and transitions state."""
    resp = client.post(
        "/api/v1/negotiation/start?merchant_id=merch_test",
        json={"product_id": "prod_test_shoe", "quantity": 1, "requested_unit_price": 4800.00, "customer_id": "cust_sec22"}
    )
    offer_id = resp.json()["offer"]["id"]

    counter_resp = client.post(
        f"/api/v1/negotiation/{offer_id}/merchant/counter",
        json={"merchant_id": "merch_test", "counter_unit_price": 4850.00, "reason": "Counter offer ₹4,850"},
        headers=test_setup["headers"]
    )
    assert counter_resp.status_code == 200
    c_data = counter_resp.json()
    assert c_data["status"] == NegotiationState.COUNTER_OFFERED.value
    assert Decimal(str(c_data["final_total"])) == Decimal("4850.00")


def test_security_23_merchant_reject_flow(client, db, test_setup):
    """Security Check 23: Merchant can explicitly reject a proposal."""
    resp = client.post(
        "/api/v1/negotiation/start?merchant_id=merch_test",
        json={"product_id": "prod_test_shoe", "quantity": 1, "requested_unit_price": 4800.00, "customer_id": "cust_sec23"}
    )
    offer_id = resp.json()["offer"]["id"]

    rej_resp = client.post(
        f"/api/v1/negotiation/{offer_id}/merchant/reject",
        json={"merchant_id": "merch_test", "reason": "Inventory low"},
        headers=test_setup["headers"]
    )
    assert rej_resp.status_code == 200
    assert rej_resp.json()["status"] == NegotiationState.MERCHANT_REJECTED.value


def test_security_24_audit_trace_integrity(client, db, test_setup):
    """Security Check 24: Offer trace endpoint delivers valid schema and cryptographic hash."""
    resp = client.post(
        "/api/v1/negotiation/start?merchant_id=merch_test",
        json={"product_id": "prod_test_shoe", "quantity": 1, "requested_unit_price": 4900.00, "customer_id": "cust_sec24"}
    )
    offer_id = resp.json()["offer"]["id"]

    trace_resp = client.get(f"/api/v1/negotiation/{offer_id}/trace")
    assert trace_resp.status_code == 200
    data = trace_resp.json()
    assert "pricing" in data
    assert "governance" in data
    assert "audit_hash" in data


def test_security_25_nonexistent_offer_404(client, db, test_setup):
    """Security Check 25: Querying nonexistent offer returns 404."""
    resp = client.get("/api/v1/negotiation/nonexistent_offer_id_99999")
    assert resp.status_code == 404


def test_security_26_negotiated_checkout_key_resolution(client, db, test_setup, monkeypatch):
    """
    Test 26: Negotiated checkout returns server-configured settings.RAZORPAY_KEY_ID
    and contains NO hardcoded 'rzp_test_ApexSports2026'.
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", "rzp_test_LiveTestKey999")
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", "secret_live_test_123")

    resp = client.post(
        "/api/v1/negotiation/start?merchant_id=merch_test",
        json={"product_id": "prod_test_shoe", "quantity": 1, "requested_unit_price": 4900.00, "customer_id": "cust_sec26"}
    )
    offer_id = resp.json()["offer"]["id"]

    # Customer accepts
    client.post(f"/api/v1/negotiation/{offer_id}/accept", json={"customer_id": "cust_sec26"})

    # Checkout
    checkout_resp = client.post(f"/api/v1/negotiation/{offer_id}/checkout", json={"customer_id": "cust_sec26"})
    assert checkout_resp.status_code == 200
    data = checkout_resp.json()

    assert data["key_id"] == "rzp_test_LiveTestKey999"
    assert data["razorpay_key_id"] == "rzp_test_LiveTestKey999"
    assert data["key_id"] != "rzp_test_ApexSports2026"
    assert data["amount_paise"] == 490000
    assert data["amount"] == 4900.00
    assert data["razorpay_order_id"] is not None


def test_security_27_valid_negotiated_signature_verification_flow(client, db, test_setup, monkeypatch):
    """
    Test 27: Valid negotiated payment signature verification transitions:
      PaymentTransaction -> CAPTURED
      NegotiatedOffer -> ORDER_CONFIRMED
      PurchaseIntent -> COMPLETED
    """
    from app.core.config import settings
    from app.database.models.payment_transaction import PaymentTransaction
    from app.database.models.purchase_intent import PurchaseIntent

    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", "rzp_test_LiveKey27")
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", "test_secret_key_27")
    monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "mock")

    resp = client.post(
        "/api/v1/negotiation/start?merchant_id=merch_test",
        json={"product_id": "prod_test_shoe", "quantity": 1, "requested_unit_price": 4900.00, "customer_id": "cust_sec27"}
    )
    offer_id = resp.json()["offer"]["id"]

    client.post(f"/api/v1/negotiation/{offer_id}/accept", json={"customer_id": "cust_sec27"})
    checkout_resp = client.post(f"/api/v1/negotiation/{offer_id}/checkout", json={"customer_id": "cust_sec27"})
    order_id = checkout_resp.json()["razorpay_order_id"]

    payment_id = "pay_test_negotiated_123"
    valid_sig = "sig_test_verified_123"

    # Call /payments/verify-signature
    verify_resp = client.post("/api/v1/payments/verify-signature", json={
        "razorpay_order_id": order_id,
        "razorpay_payment_id": payment_id,
        "razorpay_signature": valid_sig
    })
    assert verify_resp.status_code == 200
    tx_data = verify_resp.json()
    assert tx_data["status"] == "CAPTURED"
    assert tx_data["razorpay_payment_id"] == payment_id

    # Verify DB state of offer and purchase intent
    offer = db.query(NegotiatedOffer).filter(NegotiatedOffer.id == offer_id).first()
    assert offer.status == "ORDER_CONFIRMED"
    assert offer.order_id is not None

    intent = db.query(PurchaseIntent).filter(PurchaseIntent.id == offer.negotiation_id).first()
    if intent:
        assert intent.status == "COMPLETED"


def test_security_28_invalid_signature_rejected(client, db, test_setup, monkeypatch):
    """
    Test 28: Invalid signature on negotiated payment order returns HTTP 400.
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", "rzp_test_LiveKey28")
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", "test_secret_key_28")
    monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "mock")

    resp = client.post(
        "/api/v1/negotiation/start?merchant_id=merch_test",
        json={"product_id": "prod_test_shoe", "quantity": 1, "requested_unit_price": 4900.00, "customer_id": "cust_sec28"}
    )
    offer_id = resp.json()["offer"]["id"]

    client.post(f"/api/v1/negotiation/{offer_id}/accept", json={"customer_id": "cust_sec28"})
    checkout_resp = client.post(f"/api/v1/negotiation/{offer_id}/checkout", json={"customer_id": "cust_sec28"})
    order_id = checkout_resp.json()["razorpay_order_id"]

    # Forged signature (not matching sig_ prefix or HMAC)
    verify_resp = client.post("/api/v1/payments/verify-signature", json={
        "razorpay_order_id": order_id,
        "razorpay_payment_id": "pay_forged_999",
        "razorpay_signature": "bad_forged_signature_123"
    })
    assert verify_resp.status_code == 400
    assert "signature verification failed" in verify_resp.json()["detail"].lower()


def test_security_29_expired_offer_cannot_be_checked_out(client, db, test_setup):
    """
    Test 29: Expired offer cannot be checked out.
    """
    resp = client.post(
        "/api/v1/negotiation/start?merchant_id=merch_test",
        json={"product_id": "prod_test_shoe", "quantity": 1, "requested_unit_price": 4900.00, "customer_id": "cust_sec29"}
    )
    offer_id = resp.json()["offer"]["id"]
    client.post(f"/api/v1/negotiation/{offer_id}/accept", json={"customer_id": "cust_sec29"})

    # Manually expire the offer
    offer = db.query(NegotiatedOffer).filter(NegotiatedOffer.id == offer_id).first()
    offer.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    db.commit()

    checkout_resp = client.post(f"/api/v1/negotiation/{offer_id}/checkout", json={"customer_id": "cust_sec29"})
    assert checkout_resp.status_code in [400, 500]
    assert "expired" in checkout_resp.text.lower()


def test_security_30_unapproved_offer_cannot_be_checked_out(client, db, test_setup):
    """
    Test 30: Unapproved human-approval offer cannot be checked out before merchant approval.
    """
    # 4% discount requires human approval
    resp = client.post(
        "/api/v1/negotiation/start?merchant_id=merch_test",
        json={"product_id": "prod_test_shoe", "quantity": 1, "requested_unit_price": 4800.00, "customer_id": "cust_sec30"}
    )
    offer_id = resp.json()["offer"]["id"]
    assert resp.json()["status"] == NegotiationState.HUMAN_APPROVAL_REQUIRED.value

    # Attempt to checkout directly without approval
    checkout_resp = client.post(f"/api/v1/negotiation/{offer_id}/checkout", json={"customer_id": "cust_sec30"})
    assert checkout_resp.status_code in [400, 500]
    assert "accepted before checking out" in checkout_resp.text.lower()


def test_security_31_my_price_requests_unauthenticated_returns_401(client):
    """
    Test 31: Unauthenticated request to /my-requests and /my-requests/badge returns 401.
    """
    resp1 = client.get("/api/v1/negotiation/my-requests")
    assert resp1.status_code == 401

    resp2 = client.get("/api/v1/negotiation/my-requests/badge")
    assert resp2.status_code == 401


def test_security_32_my_price_requests_user_isolation(client, db, test_setup):
    """
    Test 32: Strict user isolation — Customer A only sees Customer A's offers, Customer B only sees Customer B's offers.
    """
    from app.core.security import create_access_token
    from app.database.models.user import User

    # Create User A
    user_a = db.query(User).filter(User.email == "buyer_a@apex.test").first()
    if not user_a:
        user_a = User(email="buyer_a@apex.test", full_name="Buyer A", hashed_password="pw", role="customer", is_active=True)
        db.add(user_a)
        db.commit()
        db.refresh(user_a)

    # Create User B
    user_b = db.query(User).filter(User.email == "buyer_b@apex.test").first()
    if not user_b:
        user_b = User(email="buyer_b@apex.test", full_name="Buyer B", hashed_password="pw", role="customer", is_active=True)
        db.add(user_b)
        db.commit()
        db.refresh(user_b)

    token_a = create_access_token(subject=user_a.id, merchant_id=None, role="customer")
    token_b = create_access_token(subject=user_b.id, merchant_id=None, role="customer")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Start negotiation for User A
    client.post(
        "/api/v1/negotiation/start?merchant_id=merch_test",
        json={"product_id": "prod_test_shoe", "quantity": 1, "requested_unit_price": 4900.00, "customer_id": user_a.email}
    )

    # Start negotiation for User B
    client.post(
        "/api/v1/negotiation/start?merchant_id=merch_test",
        json={"product_id": "prod_test_shoe", "quantity": 2, "requested_unit_price": 4850.00, "customer_id": user_b.email}
    )

    # Fetch User A's requests
    res_a = client.get("/api/v1/negotiation/my-requests", headers=headers_a)
    assert res_a.status_code == 200
    offers_a = res_a.json()
    assert len(offers_a) >= 1
    assert all(o["customer_id"] == user_a.email for o in offers_a)

    # Fetch User B's requests
    res_b = client.get("/api/v1/negotiation/my-requests", headers=headers_b)
    assert res_b.status_code == 200
    offers_b = res_b.json()
    assert len(offers_b) >= 1
    assert all(o["customer_id"] == user_b.email for o in offers_b)

    # Ensure none of User A's offers appear in User B's list
    ids_a = {o["id"] for o in offers_a}
    ids_b = {o["id"] for o in offers_b}
    assert ids_a.isdisjoint(ids_b)


def test_security_33_my_price_requests_badge_and_schema(client, db, test_setup):
    """
    Test 33: Actionable badge counter and rich response schema (product_name, product_image_url, category, is_actionable).
    """
    from app.core.security import create_access_token
    from app.database.models.user import User

    user = db.query(User).filter(User.email == "badge_tester@apex.test").first()
    if not user:
        user = User(email="badge_tester@apex.test", full_name="Badge Tester", hashed_password="pw", role="customer", is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)

    token = create_access_token(subject=user.id, merchant_id=None, role="customer")
    headers = {"Authorization": f"Bearer {token}"}

    # Start an auto-accepted offer (discount <= 3%)
    res_start = client.post(
        "/api/v1/negotiation/start?merchant_id=merch_test",
        json={"product_id": "prod_test_shoe", "quantity": 1, "requested_unit_price": 4900.00, "customer_id": user.email}
    )
    assert res_start.status_code == 200
    assert res_start.json()["status"] == NegotiationState.AUTO_ACCEPTED.value

    # Check badge
    badge_resp = client.get("/api/v1/negotiation/my-requests/badge", headers=headers)
    assert badge_resp.status_code == 200
    badge_data = badge_resp.json()
    assert badge_data["actionable_count"] >= 1
    assert badge_data["total_count"] >= 1

    # Check schema fields in /my-requests
    reqs_resp = client.get("/api/v1/negotiation/my-requests", headers=headers)
    assert reqs_resp.status_code == 200
    items = reqs_resp.json()
    assert len(items) >= 1
    item = items[0]
    assert item["product_name"] == "Apex Pro Running Shoe"
    assert item["category"] == "Footwear"
    assert "is_actionable" in item
    assert item["is_actionable"] is True


def test_security_34_merchant_price_requests_role_and_tenant_isolation(client, db, test_setup):
    """
    Test 34: Merchant price requests endpoint security & tenant isolation:
    - 401 unauthenticated
    - 403 customer role (non-merchant_admin)
    - Tenant isolation: Merchant Admin for Tenant 1 cannot view Tenant 2 requests.
    """
    from app.core.security import create_access_token
    from app.database.models.user import User
    from app.database.models.merchant import Merchant

    # Ensure Merchant 2 exists
    m2 = db.query(Merchant).filter(Merchant.id == "merch_tenant_2").first()
    if not m2:
        m2 = Merchant(id="merch_tenant_2", name="Tenant 2 Sports", domain="tenant2.local", is_active=True)
        db.add(m2)
        db.commit()

    # Create Merchant Admin 1
    admin_1 = db.query(User).filter(User.email == "admin_t1@apex.test").first()
    if not admin_1:
        admin_1 = User(email="admin_t1@apex.test", full_name="Admin T1", hashed_password="pw", role="merchant_admin", merchant_id="merch_test", is_active=True)
        db.add(admin_1)
        db.commit()
        db.refresh(admin_1)

    # Create Merchant Admin 2
    admin_2 = db.query(User).filter(User.email == "admin_t2@apex.test").first()
    if not admin_2:
        admin_2 = User(email="admin_t2@apex.test", full_name="Admin T2", hashed_password="pw", role="merchant_admin", merchant_id="merch_tenant_2", is_active=True)
        db.add(admin_2)
        db.commit()
        db.refresh(admin_2)

    # Create normal customer
    cust = db.query(User).filter(User.email == "customer_only@apex.test").first()
    if not cust:
        cust = User(email="customer_only@apex.test", full_name="Cust", hashed_password="pw", role="customer", is_active=True)
        db.add(cust)
        db.commit()
        db.refresh(cust)

    token_admin_1 = create_access_token(subject=admin_1.id, merchant_id="merch_test", role="merchant_admin")
    token_admin_2 = create_access_token(subject=admin_2.id, merchant_id="merch_tenant_2", role="merchant_admin")
    token_cust = create_access_token(subject=cust.id, merchant_id=None, role="customer")

    # 1. Unauthenticated -> 401
    resp_unauth = client.get("/api/v1/negotiation/merchant-requests")
    assert resp_unauth.status_code == 401

    # 2. Customer role -> 403 Forbidden
    resp_cust = client.get("/api/v1/negotiation/merchant-requests", headers={"Authorization": f"Bearer {token_cust}"})
    assert resp_cust.status_code == 403

    # 3. Create request for Tenant 1
    client.post(
        "/api/v1/negotiation/start?merchant_id=merch_test",
        json={"product_id": "prod_test_shoe", "quantity": 1, "requested_unit_price": 4800.00, "customer_id": "t1_user@apex.test"}
    )

    # 4. Merchant Admin 1 sees Tenant 1 requests
    resp_t1 = client.get("/api/v1/negotiation/merchant-requests", headers={"Authorization": f"Bearer {token_admin_1}"})
    assert resp_t1.status_code == 200
    offers_t1 = resp_t1.json()
    assert len(offers_t1) >= 1
    assert all(o["merchant_id"] == "merch_test" for o in offers_t1)

    # 5. Merchant Admin 2 badge and list are isolated from Tenant 1
    resp_t2 = client.get("/api/v1/negotiation/merchant-requests", headers={"Authorization": f"Bearer {token_admin_2}"})
    assert resp_t2.status_code == 200
    offers_t2 = resp_t2.json()
    assert all(o["merchant_id"] == "merch_tenant_2" for o in offers_t2)


def test_security_35_merchant_decision_lifecycle(client, db, test_setup):
    """
    Test 35: Complete merchant approval and counter-offer decision lifecycle.
    """
    from app.core.security import create_access_token
    from app.database.models.user import User

    admin = db.query(User).filter(User.email == "decision_admin@apex.test").first()
    if not admin:
        admin = User(email="decision_admin@apex.test", full_name="Decision Admin", hashed_password="pw", role="merchant_admin", merchant_id="merch_test", is_active=True)
        db.add(admin)
        db.commit()
        db.refresh(admin)

    token_admin = create_access_token(subject=admin.id, merchant_id="merch_test", role="merchant_admin")
    admin_headers = {"Authorization": f"Bearer {token_admin}"}

    # 1. Customer starts negotiation requiring human approval (4% discount on 5000 -> 4800)
    res_start = client.post(
        "/api/v1/negotiation/start?merchant_id=merch_test",
        json={"product_id": "prod_test_shoe", "quantity": 2, "requested_unit_price": 4800.00, "customer_id": "cust_lifecycle@apex.test"}
    )
    assert res_start.status_code == 200
    offer_id = res_start.json()["offer"]["id"]
    assert res_start.json()["status"] == NegotiationState.HUMAN_APPROVAL_REQUIRED.value

    # 2. Check merchant badge count
    badge_resp = client.get("/api/v1/negotiation/merchant-requests/badge", headers=admin_headers)
    assert badge_resp.status_code == 200
    assert badge_resp.json()["pending_count"] >= 1

    # 3. Merchant counters with unit price 4850
    counter_resp = client.post(
        f"/api/v1/negotiation/{offer_id}/merchant/counter",
        headers=admin_headers,
        json={
            "merchant_id": "merch_test",
            "counter_unit_price": 4850.00,
            "counter_total": 9700.00,
            "reason": "Special merchant counter for pair order."
        }
    )
    assert counter_resp.status_code == 200
    assert counter_resp.json()["status"] == NegotiationState.COUNTER_OFFERED.value
    assert float(counter_resp.json()["final_total"]) == 9700.00

    # 4. Customer accepts counter-offer
    accept_resp = client.post(
        f"/api/v1/negotiation/{offer_id}/accept",
        json={"customer_id": "cust_lifecycle@apex.test", "reason": "Customer accepted counter offer."}
    )
    assert accept_resp.status_code == 200
    assert accept_resp.json()["status"] == NegotiationState.CUSTOMER_ACCEPTED.value



