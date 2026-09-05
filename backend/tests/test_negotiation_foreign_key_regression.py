import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.database.models.user import User
from app.database.models.product import Product
from app.database.models.merchant import Merchant
from app.database.models.policy import Policy
from app.database.models.negotiation_policy import MerchantNegotiationPolicy
from app.database.models.policy_evaluation import PolicyEvaluation
from app.database.models.approval_request import ApprovalRequest
from app.database.models.negotiated_offer import NegotiatedOffer
from app.database.models.audit_event import AuditEvent
from app.negotiation.engine import NegotiationEngine
from app.negotiation.state_machine import NegotiationState
from scripts.seed import seed_db


@pytest.fixture(autouse=True)
def seeded_env(db: Session):
    """Ensure canonical seed runs before tests in this module."""
    seed_db(reset=False, db_session=db)
    return db


def test_a_canonical_negotiation_policy_exists(db: Session):
    """Test A: Canonical negotiation policy exists in both policies and merchant_negotiation_policies tables."""
    canonical_id = "da3fac75-b80d-4e38-b3eb-9a94dd64d242"
    
    # 1. Check policies table (governance & FK target)
    gov_policy = db.query(Policy).filter(Policy.id == canonical_id).first()
    assert gov_policy is not None, "Canonical negotiation policy missing from policies table"
    assert gov_policy.max_discount_percent == Decimal("5.00")
    assert gov_policy.allowed_currency == "INR"
    assert gov_policy.is_active is True
    assert gov_policy.version == 1

    # 2. Check merchant_negotiation_policies table
    neg_policy = db.query(MerchantNegotiationPolicy).filter(MerchantNegotiationPolicy.id == canonical_id).first()
    assert neg_policy is not None, "Canonical negotiation policy missing from merchant_negotiation_policies table"
    assert neg_policy.enabled is True
    assert neg_policy.max_discount_percent == Decimal("5.00")
    assert neg_policy.auto_accept_below_discount_percent == Decimal("3.00")
    assert neg_policy.approval_above_discount_percent == Decimal("3.00")
    assert neg_policy.currency == "INR"
    assert neg_policy.is_active is True


def test_b_policy_evaluations_insert_succeeds_on_human_approval(db: Session):
    """Test B: When negotiation requires human approval (3% < discount <= 5%), PolicyEvaluation is inserted with valid FK."""
    merchant = db.query(Merchant).filter(Merchant.name == "Apex Sports Merchant").first()
    product = db.query(Product).filter(Product.merchant_id == merchant.id, Product.is_active == True).first()
    assert product is not None

    # Request a 4.0% discount (which falls in (3.0%, 5.0%], requiring human approval)
    list_price = Decimal(str(product.price))
    requested_total = (list_price * Decimal("0.96")).quantize(Decimal("0.01"))

    offer, result = NegotiationEngine.evaluate_negotiation(
        db=db,
        merchant=merchant,
        product=product,
        quantity=1,
        requested_total=requested_total,
        buyer_user_id="cust_test_b@example.com",
        buyer_message="Requesting 4% discount please",
        trace_id="trc_test_b_001"
    )

    assert offer.status == NegotiationState.HUMAN_APPROVAL_REQUIRED.value
    assert result["decision"] == "HUMAN_APPROVAL"
    assert offer.governance_evaluation_id is not None

    # Verify PolicyEvaluation row exists and correctly references Policy
    eval_row = db.query(PolicyEvaluation).filter(PolicyEvaluation.id == offer.governance_evaluation_id).first()
    assert eval_row is not None
    assert eval_row.policy_id == "da3fac75-b80d-4e38-b3eb-9a94dd64d242"
    assert eval_row.decision == "REQUIRES_APPROVAL"
    assert eval_row.requires_human_approval is True
    assert eval_row.merchant_id == merchant.id

    # Verify ApprovalRequest row exists
    appr_row = db.query(ApprovalRequest).filter(ApprovalRequest.id == offer.merchant_approval_request_id).first()
    assert appr_row is not None
    assert appr_row.policy_evaluation_id == eval_row.id
    assert appr_row.status == "PENDING"


def test_c_negotiation_reaches_valid_counter_offer_when_discount_exceeds_max(db: Session):
    """Test C: When discount requested > max_discount_percent (e.g. 15% > 5%), engine creates COUNTER_OFFER at 5%."""
    merchant = db.query(Merchant).filter(Merchant.name == "Apex Sports Merchant").first()
    product = db.query(Product).filter(Product.merchant_id == merchant.id, Product.is_active == True).first()

    # Request 15% discount
    list_price = Decimal(str(product.price))
    requested_total = (list_price * Decimal("0.85")).quantize(Decimal("0.01"))

    offer, result = NegotiationEngine.evaluate_negotiation(
        db=db,
        merchant=merchant,
        product=product,
        quantity=1,
        requested_total=requested_total,
        buyer_user_id="cust_test_c@example.com",
        buyer_message="Can I get 15% off?",
        trace_id="trc_test_c_001"
    )

    assert offer.status == NegotiationState.COUNTER_OFFERED.value
    assert result["decision"] == "COUNTER"
    assert offer.discount_percent == Decimal("5.00")
    expected_counter = (list_price * Decimal("0.95")).quantize(Decimal("0.01"))
    assert offer.final_total == expected_counter


def test_d_merchant_approval_workflow(db: Session):
    """Test D: Merchant admin approves a pending human approval offer, moving it to AUTO_ACCEPTED and binding valid User UUID."""
    merchant = db.query(Merchant).filter(Merchant.name == "Apex Sports Merchant").first()
    product = db.query(Product).filter(Product.merchant_id == merchant.id, Product.is_active == True).first()
    demo_merchant = db.query(User).filter(User.email == "demo-merchant@apex.test").first()
    assert demo_merchant is not None

    list_price = Decimal(str(product.price))
    requested_total = (list_price * Decimal("0.96")).quantize(Decimal("0.01"))

    offer, _ = NegotiationEngine.evaluate_negotiation(
        db=db,
        merchant=merchant,
        product=product,
        quantity=1,
        requested_total=requested_total,
        buyer_user_id="cust_test_d@example.com",
        trace_id="trc_test_d_001"
    )
    assert offer.status == NegotiationState.HUMAN_APPROVAL_REQUIRED.value

    # Merchant admin approves using demo_merchant.id (UUID)
    approved_offer = NegotiationEngine.merchant_approve_offer(
        db=db,
        offer_id=offer.id,
        merchant_id=merchant.id,
        admin_user_id=demo_merchant.id,
        reason="Approved by store manager"
    )

    assert approved_offer.status in [NegotiationState.MERCHANT_APPROVED.value, NegotiationState.AUTO_ACCEPTED.value]
    assert approved_offer.merchant_decision == "APPROVED"

    # Verify ApprovalRequest updated and approved_by_user_id is the exact User UUID (foreign key compliant)
    appr = db.query(ApprovalRequest).filter(ApprovalRequest.id == approved_offer.merchant_approval_request_id).first()
    assert appr.status == "APPROVED"
    assert appr.approved_by_user_id == demo_merchant.id
    assert appr.approved_by_user_id != demo_merchant.email


def test_e_excessive_discount_or_zero_price_handled_safely(db: Session):
    """Test E: Zero or negative prices are cleanly rejected with audit recording."""
    merchant = db.query(Merchant).filter(Merchant.name == "Apex Sports Merchant").first()
    product = db.query(Product).filter(Product.merchant_id == merchant.id, Product.is_active == True).first()

    offer, result = NegotiationEngine.evaluate_negotiation(
        db=db,
        merchant=merchant,
        product=product,
        quantity=1,
        requested_total=Decimal("0.00"),
        buyer_user_id="cust_test_e@example.com",
        trace_id="trc_test_e_001"
    )

    assert offer.status == NegotiationState.REJECTED.value
    assert result["decision"] == "REJECT"


def test_f_customer_acceptance_workflow(db: Session):
    """Test F: Customer can accept an AUTO_ACCEPTED or COUNTER_OFFERED offer."""
    merchant = db.query(Merchant).filter(Merchant.name == "Apex Sports Merchant").first()
    product = db.query(Product).filter(Product.merchant_id == merchant.id, Product.is_active == True).first()

    # Request 2% discount (auto-accepted)
    list_price = Decimal(str(product.price))
    requested_total = (list_price * Decimal("0.98")).quantize(Decimal("0.01"))

    offer, _ = NegotiationEngine.evaluate_negotiation(
        db=db,
        merchant=merchant,
        product=product,
        quantity=1,
        requested_total=requested_total,
        buyer_user_id="cust_test_f@example.com",
        trace_id="trc_test_f_001"
    )
    assert offer.status == NegotiationState.AUTO_ACCEPTED.value

    # Customer accepts
    accepted_offer = NegotiationEngine.customer_accept_offer(
        db=db,
        offer_id=offer.id,
        customer_id="cust_test_f@example.com",
        reason="I accept the deal"
    )

    assert accepted_offer.status == NegotiationState.CUSTOMER_ACCEPTED.value
    assert accepted_offer.customer_accepted_at is not None


def test_g_checkout_razorpay_amount_is_server_authoritative(db: Session):
    """Test G: Checkout enforces server-authoritative offer price and rejects tampering."""
    merchant = db.query(Merchant).filter(Merchant.name == "Apex Sports Merchant").first()
    product = db.query(Product).filter(Product.merchant_id == merchant.id, Product.is_active == True).first()

    list_price = Decimal(str(product.price))
    requested_total = (list_price * Decimal("0.98")).quantize(Decimal("0.01"))

    offer, _ = NegotiationEngine.evaluate_negotiation(
        db=db,
        merchant=merchant,
        product=product,
        quantity=1,
        requested_total=requested_total,
        buyer_user_id="cust_test_g@example.com",
        trace_id="trc_test_g_001"
    )
    NegotiationEngine.customer_accept_offer(db=db, offer_id=offer.id, customer_id="cust_test_g@example.com")

    # Attempt checkout with tampered lower amount -> should raise ValueError
    with pytest.raises(ValueError, match="Price mismatch"):
        NegotiationEngine.checkout_negotiated_offer(
            db=db,
            offer_id=offer.id,
            buyer_user_id="cust_test_g@example.com",
            merchant_id=merchant.id,
            client_amount=Decimal("1.00")
        )

    # Valid checkout with authoritative amount
    checkout_res = NegotiationEngine.checkout_negotiated_offer(
        db=db,
        offer_id=offer.id,
        buyer_user_id="cust_test_g@example.com",
        merchant_id=merchant.id,
        client_amount=offer.final_total
    )

    assert checkout_res["status"] == "payment_ready"
    assert checkout_res["amount"] == float(requested_total)
    assert checkout_res["razorpay_order_id"] is not None


def test_h_no_duplicate_policy_when_seeding_twice(db: Session):
    """Test H: Seeding database multiple times preserves exactly 1 canonical policy and does not duplicate."""
    # Seed already ran in fixture, run it again
    res1 = seed_db(reset=False, db_session=db)
    res2 = seed_db(reset=False, db_session=db)

    canonical_id = "da3fac75-b80d-4e38-b3eb-9a94dd64d242"
    gov_policies = db.query(Policy).filter(Policy.id == canonical_id).all()
    assert len(gov_policies) == 1, "Duplicate canonical Policy in policies table"

    neg_policies = db.query(MerchantNegotiationPolicy).filter(MerchantNegotiationPolicy.id == canonical_id).all()
    assert len(neg_policies) == 1, "Duplicate canonical MerchantNegotiationPolicy"


def test_i_tenant_isolation_remains_intact(db: Session):
    """Test I: Merchant B cannot approve an offer belonging to Merchant A."""
    merchant_a = db.query(Merchant).filter(Merchant.name == "Apex Sports Merchant").first()
    product = db.query(Product).filter(Product.merchant_id == merchant_a.id, Product.is_active == True).first()

    # Create Merchant B
    merchant_b = Merchant(
        id="merch_other_tenant",
        name="Other Merchant",
        domain="other.test",
        is_active=True
    )
    db.add(merchant_b)
    db.flush()

    list_price = Decimal(str(product.price))
    requested_total = (list_price * Decimal("0.96")).quantize(Decimal("0.01"))

    offer, _ = NegotiationEngine.evaluate_negotiation(
        db=db,
        merchant=merchant_a,
        product=product,
        quantity=1,
        requested_total=requested_total,
        buyer_user_id="cust_test_i@example.com",
        trace_id="trc_test_i_001"
    )

    # Merchant B attempts to approve Merchant A's offer
    with pytest.raises(ValueError, match="Tenant mismatch"):
        NegotiationEngine.merchant_approve_offer(
            db=db,
            offer_id=offer.id,
            merchant_id=merchant_b.id,
            admin_user_id="admin@other.test"
        )


def test_j_audit_events_recorded_with_trace_id(db: Session):
    """Test J: Audit events are deterministically written to audit_events with matching trace_id."""
    merchant = db.query(Merchant).filter(Merchant.name == "Apex Sports Merchant").first()
    product = db.query(Product).filter(Product.merchant_id == merchant.id, Product.is_active == True).first()

    trace = "trc_audit_verification_999"
    list_price = Decimal(str(product.price))
    requested_total = (list_price * Decimal("0.98")).quantize(Decimal("0.01"))

    offer, _ = NegotiationEngine.evaluate_negotiation(
        db=db,
        merchant=merchant,
        product=product,
        quantity=1,
        requested_total=requested_total,
        buyer_user_id="cust_test_j@example.com",
        trace_id=trace
    )

    events = db.query(AuditEvent).filter(AuditEvent.trace_id == trace).all()
    assert len(events) >= 2
    actions = [e.action for e in events]
    assert "START_NEGOTIATION" in actions
    assert "AUTO_ACCEPT_NEGOTIATION" in actions


def test_k_merchant_approval_resolves_email_to_user_uuid_and_never_stores_raw_email(db: Session):
    """Test K: Passing merchant email to merchant_approve automatically resolves to user.id (UUID) and never stores email."""
    merchant = db.query(Merchant).filter(Merchant.name == "Apex Sports Merchant").first()
    product = db.query(Product).filter(Product.merchant_id == merchant.id, Product.is_active == True).first()
    demo_merchant = db.query(User).filter(User.email == "demo-merchant@apex.test").first()
    assert demo_merchant is not None

    list_price = Decimal(str(product.price))
    requested_total = (list_price * Decimal("0.96")).quantize(Decimal("0.01"))

    offer, _ = NegotiationEngine.evaluate_negotiation(
        db=db,
        merchant=merchant,
        product=product,
        quantity=1,
        requested_total=requested_total,
        buyer_user_id="cust_test_k@example.com",
        trace_id="trc_test_k_001"
    )

    # Approve by passing email string "demo-merchant@apex.test"
    approved_offer = NegotiationEngine.merchant_approve(
        db=db,
        offer_id=offer.id,
        merchant_id=merchant.id,
        approver_email="demo-merchant@apex.test",
        reason="Approving via email lookup"
    )

    assert approved_offer.status in [NegotiationState.MERCHANT_APPROVED.value, NegotiationState.AUTO_ACCEPTED.value]
    appr = db.query(ApprovalRequest).filter(ApprovalRequest.id == approved_offer.merchant_approval_request_id).first()
    assert appr is not None
    assert appr.status == "APPROVED"
    assert appr.approved_by_user_id == demo_merchant.id
    assert appr.approved_by_user_id != "demo-merchant@apex.test"


def test_l_merchant_counter_resolves_user_uuid(db: Session):
    """Test L: Countering an offer sets approved_by_user_id to the merchant User UUID."""
    merchant = db.query(Merchant).filter(Merchant.name == "Apex Sports Merchant").first()
    product = db.query(Product).filter(Product.merchant_id == merchant.id, Product.is_active == True).first()
    demo_merchant = db.query(User).filter(User.email == "demo-merchant@apex.test").first()
    assert demo_merchant is not None

    list_price = Decimal(str(product.price))
    requested_total = (list_price * Decimal("0.96")).quantize(Decimal("0.01"))

    offer, _ = NegotiationEngine.evaluate_negotiation(
        db=db,
        merchant=merchant,
        product=product,
        quantity=1,
        requested_total=requested_total,
        buyer_user_id="cust_test_l@example.com",
        trace_id="trc_test_l_001"
    )

    counter_total = (list_price * Decimal("0.97")).quantize(Decimal("0.01"))
    countered_offer = NegotiationEngine.merchant_counter_offer(
        db=db,
        offer_id=offer.id,
        merchant_id=merchant.id,
        admin_user_id=demo_merchant.id,
        counter_total=counter_total,
        message="Countering with 3% discount"
    )

    assert countered_offer.status == NegotiationState.COUNTER_OFFERED.value
    appr = db.query(ApprovalRequest).filter(ApprovalRequest.id == countered_offer.merchant_approval_request_id).first()
    assert appr is not None
    assert appr.approved_by_user_id == demo_merchant.id


def test_m_customer_forbidden_from_merchant_endpoints_403(client, db):
    """Test M: Customer role receives 403 Forbidden when calling merchant approval/counter/reject endpoints."""
    from app.core.security import create_access_token
    customer = db.query(User).filter(User.email == "customer@demo-sports.test").first()
    assert customer is not None
    assert customer.role == "customer"

    token = create_access_token(subject=customer.id, merchant_id=customer.merchant_id, role=customer.role)
    headers = {"Authorization": f"Bearer {token}"}

    # Attempt to call merchant approve
    resp = client.post(
        "/api/v1/negotiation/fake_offer_id/merchant/approve",
        json={"merchant_id": customer.merchant_id, "reason": "Rogue approval"},
        headers=headers
    )
    assert resp.status_code == 403
    assert "privileges required" in resp.json()["detail"].lower() or "merchant" in resp.json()["detail"].lower()


def test_n_unauthenticated_forbidden_from_merchant_endpoints_401(client):
    """Test N: Unauthenticated requests receive 401 Unauthorized when calling merchant approval endpoints."""
    resp = client.post(
        "/api/v1/negotiation/fake_offer_id/merchant/approve",
        json={"merchant_id": "merch_default", "reason": "No auth"}
    )
    assert resp.status_code == 401


def test_o_approver_user_not_found_raises_clean_error(db: Session):
    """Test O: If an invalid/non-existent user ID is passed to merchant_approve_offer, a clean ValueError is raised."""
    merchant = db.query(Merchant).filter(Merchant.name == "Apex Sports Merchant").first()
    product = db.query(Product).filter(Product.merchant_id == merchant.id, Product.is_active == True).first()

    list_price = Decimal(str(product.price))
    requested_total = (list_price * Decimal("0.96")).quantize(Decimal("0.01"))

    offer, _ = NegotiationEngine.evaluate_negotiation(
        db=db,
        merchant=merchant,
        product=product,
        quantity=1,
        requested_total=requested_total,
        buyer_user_id="cust_test_o@example.com",
        trace_id="trc_test_o_001"
    )

    with pytest.raises(ValueError, match="Approver user record not found"):
        NegotiationEngine.merchant_approve_offer(
            db=db,
            offer_id=offer.id,
            merchant_id=merchant.id,
            admin_user_id="non_existent_user_12345",
            reason="Should fail cleanly"
        )


def test_p_pdp_validation_active_counter_offer(client, db: Session):
    """Test P: Validates that /validate-pdp endpoint returns authoritative counter-offer pricing and payable state."""
    merchant = db.query(Merchant).filter(Merchant.name == "Apex Sports Merchant").first()
    product = db.query(Product).filter(Product.merchant_id == merchant.id, Product.is_active == True).first()

    # Request 10% discount -> triggers counter-offer at 5% max
    list_price = Decimal(str(product.price))
    requested_total = (list_price * Decimal("0.90")).quantize(Decimal("0.01"))

    offer, result = NegotiationEngine.evaluate_negotiation(
        db=db,
        merchant=merchant,
        product=product,
        quantity=1,
        requested_total=requested_total,
        buyer_user_id="customer@demo-sports.test",
        trace_id="trc_test_p_001"
    )
    assert offer.status == NegotiationState.COUNTER_OFFERED.value

    # Call validate-pdp
    resp = client.get(f"/api/v1/negotiation/{offer.id}/validate-pdp?product_id={product.id}")
    assert resp.status_code == 200
    data = resp.json()

    assert data["offer_id"] == offer.id
    assert data["product_id"] == product.id
    assert data["is_payable"] is True
    assert data["is_counter"] is True
    assert data["is_expired"] is False
    assert data["final_total"] == float(offer.final_total)
    assert data["discount_percent"] == float(offer.discount_percent)
    assert data["seconds_remaining"] > 0


def test_q_pdp_validation_product_mismatch_returns_400(client, db: Session):
    """Test Q: Calling /validate-pdp with a mismatched product_id returns 400 Bad Request."""
    merchant = db.query(Merchant).filter(Merchant.name == "Apex Sports Merchant").first()
    product = db.query(Product).filter(Product.merchant_id == merchant.id, Product.is_active == True).first()

    offer, _ = NegotiationEngine.evaluate_negotiation(
        db=db,
        merchant=merchant,
        product=product,
        quantity=1,
        requested_total=Decimal(str(product.price * Decimal("0.98"))).quantize(Decimal("0.01")),
        buyer_user_id="customer@demo-sports.test",
        trace_id="trc_test_q_001"
    )

    resp = client.get(f"/api/v1/negotiation/{offer.id}/validate-pdp?product_id=prod_completely_wrong_id")
    assert resp.status_code == 400
    assert "different product" in resp.json()["detail"].lower() or "mismatch" in resp.json()["detail"].lower()


def test_r_pdp_validation_unauthorized_customer_returns_403(client, db: Session):
    """Test R: Authenticated user who does not own the offer is blocked with 403 Forbidden."""
    from app.core.security import create_access_token

    merchant = db.query(Merchant).filter(Merchant.name == "Apex Sports Merchant").first()
    product = db.query(Product).filter(Product.merchant_id == merchant.id, Product.is_active == True).first()

    # Offer belongs to customer@demo-sports.test
    offer, _ = NegotiationEngine.evaluate_negotiation(
        db=db,
        merchant=merchant,
        product=product,
        quantity=1,
        requested_total=Decimal(str(product.price * Decimal("0.98"))).quantize(Decimal("0.01")),
        buyer_user_id="customer@demo-sports.test",
        trace_id="trc_test_r_001"
    )

    # Intruder user
    intruder = User(
        email="intruder@other.test",
        full_name="Intruder User",
        hashed_password="hash",
        role="customer",
        is_active=True
    )
    db.add(intruder)
    db.commit()
    db.refresh(intruder)

    token = create_access_token(subject=intruder.id, merchant_id=None, role=intruder.role)
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get(f"/api/v1/negotiation/{offer.id}/validate-pdp?product_id={product.id}", headers=headers)
    assert resp.status_code == 403
    assert "access denied" in resp.json()["detail"].lower() or "permission" in resp.json()["detail"].lower()


def test_s_pdp_validation_expired_offer_marked_not_payable(client, db: Session):
    """Test S: Expired offer returns is_expired=True and is_payable=False."""
    merchant = db.query(Merchant).filter(Merchant.name == "Apex Sports Merchant").first()
    product = db.query(Product).filter(Product.merchant_id == merchant.id, Product.is_active == True).first()

    past_time = datetime.now(timezone.utc) - timedelta(hours=2)
    offer = NegotiatedOffer(
        tenant_id=merchant.id,
        negotiation_id="neg_expired_test_s",
        buyer_user_id="customer@demo-sports.test",
        merchant_id=merchant.id,
        product_id=product.id,
        quantity=1,
        list_price=Decimal(str(product.price)),
        list_total=Decimal(str(product.price)),
        requested_total=Decimal(str(product.price * Decimal("0.98"))).quantize(Decimal("0.01")),
        final_total=Decimal(str(product.price * Decimal("0.98"))).quantize(Decimal("0.01")),
        discount_amount=Decimal(str(product.price * Decimal("0.02"))).quantize(Decimal("0.01")),
        discount_percent=Decimal("2.00"),
        currency="INR",
        status=NegotiationState.AUTO_ACCEPTED.value,
        expires_at=past_time,
        trace_id="trc_expired_test_s"
    )
    db.add(offer)
    db.commit()
    db.refresh(offer)

    resp = client.get(f"/api/v1/negotiation/{offer.id}/validate-pdp?product_id={product.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_expired"] is True
    assert data["is_payable"] is False
    assert data["seconds_remaining"] == 0


def test_t_pdp_validation_declined_offer_not_payable(client, db: Session):
    """Test T: Declined offer returns is_declined=True and is_payable=False."""
    merchant = db.query(Merchant).filter(Merchant.name == "Apex Sports Merchant").first()
    product = db.query(Product).filter(Product.merchant_id == merchant.id, Product.is_active == True).first()

    offer = NegotiatedOffer(
        tenant_id=merchant.id,
        negotiation_id="neg_declined_test_t",
        buyer_user_id="customer@demo-sports.test",
        merchant_id=merchant.id,
        product_id=product.id,
        quantity=1,
        list_price=Decimal(str(product.price)),
        list_total=Decimal(str(product.price)),
        requested_total=Decimal(str(product.price * Decimal("0.50"))).quantize(Decimal("0.01")),
        final_total=Decimal(str(product.price)),
        discount_amount=Decimal("0.00"),
        discount_percent=Decimal("0.00"),
        currency="INR",
        status=NegotiationState.CUSTOMER_REJECTED.value,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        trace_id="trc_declined_test_t"
    )
    db.add(offer)
    db.commit()
    db.refresh(offer)

    resp = client.get(f"/api/v1/negotiation/{offer.id}/validate-pdp?product_id={product.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_declined"] is True
    assert data["is_payable"] is False


def test_u_pdp_direct_counter_checkout_success(client, db: Session):
    """Test U: Customer accepting counter-offer on PDP transitions offer to accepted and creates locked payment order."""
    merchant = db.query(Merchant).filter(Merchant.name == "Apex Sports Merchant").first()
    product = db.query(Product).filter(Product.merchant_id == merchant.id, Product.is_active == True).first()

    # Request 10% discount -> generates 5% counter-offer
    list_price = Decimal(str(product.price))
    requested_total = (list_price * Decimal("0.90")).quantize(Decimal("0.01"))

    offer, _ = NegotiationEngine.evaluate_negotiation(
        db=db,
        merchant=merchant,
        product=product,
        quantity=1,
        requested_total=requested_total,
        buyer_user_id="customer@demo-sports.test",
        trace_id="trc_test_u_001"
    )
    assert offer.status == NegotiationState.COUNTER_OFFERED.value

    # Accept counter offer
    accept_resp = client.post(
        f"/api/v1/negotiation/{offer.id}/accept",
        json={"customer_id": "customer@demo-sports.test"}
    )
    assert accept_resp.status_code == 200

    # Checkout
    resp = client.post(
        f"/api/v1/negotiation/{offer.id}/checkout",
        json={"customer_id": "customer@demo-sports.test", "payment_method": "upi"}
    )
    assert resp.status_code == 200
    chk_data = resp.json()
    assert "razorpay_order_id" in chk_data
    assert chk_data["amount"] == float(offer.final_total)

    # Verify offer status transitioned to CUSTOMER_ACCEPTED or PAYMENT_PENDING
    db.expire_all()
    updated_offer = db.query(NegotiatedOffer).filter(NegotiatedOffer.id == offer.id).first()
    assert updated_offer.status in [NegotiationState.CUSTOMER_ACCEPTED.value, NegotiationState.PAYMENT_PENDING.value]

