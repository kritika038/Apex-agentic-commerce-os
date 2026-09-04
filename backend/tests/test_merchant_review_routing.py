import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta

from app.database.models.base import Base
from app.database.models.merchant import Merchant
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.user import User
from app.database.models.cart import Cart, CartItem
from app.database.models.purchase_intent import PurchaseIntent
from app.database.models.policy_evaluation import PolicyEvaluation
from app.database.models.approval_request import ApprovalRequest
from app.database.models.negotiated_offer import NegotiatedOffer
from app.database.models.negotiation_policy import MerchantNegotiationPolicy
from app.negotiation.state_machine import NegotiationState
from app.negotiation.engine import NegotiationEngine


@pytest.fixture
def seed_data(db):
    # Seed merchant
    merchant = Merchant(id="m_merch_test", name="Apex Activewear", domain="activewear.apex.test", is_active=True)
    db.add(merchant)

    # Seed product with list price ₹399 and inventory
    product = Product(
        id="prod_socks_399",
        merchant_id="m_merch_test",
        name="Performance Running Socks",
        description="High performance anti-blister socks",
        category="Apparel",
        price=Decimal("399.00"),
        currency="INR",
        is_active=True
    )
    db.add(product)
    db.flush()

    inventory = Inventory(
        merchant_id="m_merch_test",
        product_id="prod_socks_399",
        stock_quantity=50,
        reserved_quantity=0
    )
    db.add(inventory)

    # Seed merchant policy: min_order_value = 500.00, auto_accept = 3.0%, max_discount = 15.0%
    policy = MerchantNegotiationPolicy(
        tenant_id="m_merch_test",
        merchant_id="m_merch_test",
        name="Activewear Negotiation Policy",
        enabled=True,
        max_discount_percent=Decimal("15.00"),
        max_discount_amount=Decimal("1000.00"),
        auto_accept_below_discount_percent=Decimal("3.00"),
        approval_above_discount_percent=Decimal("3.00"),
        max_quantity=5,
        min_order_value=Decimal("500.00"),
        allowed_categories=[],
        allowed_products=[],
        currency="INR",
        offer_ttl_minutes=60,
        is_active=True
    )
    db.add(policy)

    # Seed users
    cust_user = User(
        id="user_cust_123",
        email="customer123@apex.test",
        full_name="Kritika Customer",
        hashed_password="hashed_pw_dummy",
        role="CUSTOMER",
        is_active=True
    )
    cust_user2 = User(
        id="user_cust_456",
        email="othercustomer@apex.test",
        full_name="Other Customer",
        hashed_password="hashed_pw_dummy",
        role="CUSTOMER",
        is_active=True
    )
    merch_user = User(
        id="user_merch_123",
        email="merchant@apex.test",
        full_name="Merchant Admin",
        hashed_password="hashed_pw_dummy",
        role="MERCHANT",
        is_active=True
    )
    db.add(cust_user)
    db.add(cust_user2)
    db.add(merch_user)

    db.commit()


def test_sub_threshold_price_request_routes_to_merchant_review(db, seed_data):
    """
    User-reported bug:
    Product: Performance Socks (₹399 list price)
    Customer requested: ₹200 (49.87% discount)
    Min order value threshold: ₹500.00

    EXPECTED: Must NOT be auto-declined.
    Must route to HUMAN_APPROVAL_REQUIRED and generate an ApprovalRequest & PolicyEvaluation.
    """
    offer = NegotiationEngine.start_negotiation(
        db=db,
        merchant_id="m_merch_test",
        customer_id="user_cust_123",
        product_id="prod_socks_399",
        quantity=1,
        requested_unit_price=Decimal("200.00"),
        buyer_note="Can I get a student discount?"
    )

    assert offer.status == NegotiationState.HUMAN_APPROVAL_REQUIRED.value
    assert offer.list_price == Decimal("399.00")
    assert offer.list_total == Decimal("399.00")
    assert offer.requested_total == Decimal("200.00")
    assert offer.discount_percent == Decimal("49.87")
    assert offer.merchant_approval_request_id is not None
    assert offer.governance_evaluation_id is not None

    # Check that ApprovalRequest exists and is PENDING
    appr = db.query(ApprovalRequest).filter(ApprovalRequest.id == offer.merchant_approval_request_id).first()
    assert appr is not None
    assert appr.status == "PENDING"
    assert appr.merchant_id == "m_merch_test"

    # Check that PolicyEvaluation exists with appropriate violation note
    eval_rec = db.query(PolicyEvaluation).filter(PolicyEvaluation.id == offer.governance_evaluation_id).first()
    assert eval_rec is not None
    assert eval_rec.decision == "REQUIRES_APPROVAL"
    assert any("below standard auto-accept threshold" in v for v in eval_rec.violations)


def test_merchant_can_approve_escalated_request(db, seed_data):
    """
    Merchant reviews and approves the sub-threshold request.
    """
    offer = NegotiationEngine.start_negotiation(
        db=db,
        merchant_id="m_merch_test",
        customer_id="user_cust_123",
        product_id="prod_socks_399",
        quantity=1,
        requested_unit_price=Decimal("200.00"),
        buyer_note="Special request"
    )
    assert offer.status == NegotiationState.HUMAN_APPROVAL_REQUIRED.value

    approved_offer = NegotiationEngine.merchant_approve_offer(
        db=db,
        offer_id=offer.id,
        merchant_id="m_merch_test",
        admin_user_id="user_merch_123",
        reason="Approved for promotion"
    )

    assert approved_offer.status in [NegotiationState.AUTO_ACCEPTED.value, NegotiationState.MERCHANT_APPROVED.value]
    assert approved_offer.final_total == Decimal("200.00")
    assert approved_offer.merchant_decision == "APPROVED"

    # Verify ApprovalRequest status is updated to APPROVED
    appr = db.query(ApprovalRequest).filter(ApprovalRequest.id == offer.merchant_approval_request_id).first()
    assert appr.status == "APPROVED"
    assert appr.approved_by_user_id == "user_merch_123"


def test_merchant_can_counter_escalated_request(db, seed_data):
    """
    Merchant reviews and sends counter-offer of ₹280.
    """
    offer = NegotiationEngine.start_negotiation(
        db=db,
        merchant_id="m_merch_test",
        customer_id="user_cust_123",
        product_id="prod_socks_399",
        quantity=1,
        requested_unit_price=Decimal("200.00")
    )
    assert offer.status == NegotiationState.HUMAN_APPROVAL_REQUIRED.value

    countered_offer = NegotiationEngine.merchant_counter_offer(
        db=db,
        offer_id=offer.id,
        merchant_id="m_merch_test",
        admin_user_id="user_merch_123",
        counter_total=Decimal("280.00"),
        message="Best we can do is ₹280"
    )

    assert countered_offer.status == NegotiationState.COUNTER_OFFERED.value
    assert countered_offer.merchant_counter_total == Decimal("280.00")
    assert countered_offer.final_total == Decimal("280.00")


def test_merchant_can_decline_escalated_request(db, seed_data):
    """
    Merchant reviews and declines the request -> moves to MERCHANT_REJECTED.
    """
    offer = NegotiationEngine.start_negotiation(
        db=db,
        merchant_id="m_merch_test",
        customer_id="user_cust_123",
        product_id="prod_socks_399",
        quantity=1,
        requested_unit_price=Decimal("200.00")
    )
    assert offer.status == NegotiationState.HUMAN_APPROVAL_REQUIRED.value

    rejected_offer = NegotiationEngine.merchant_reject_offer(
        db=db,
        offer_id=offer.id,
        merchant_id="m_merch_test",
        admin_user_id="user_merch_123",
        reason="Discount too deep for low quantity"
    )

    assert rejected_offer.status == NegotiationState.MERCHANT_REJECTED.value
    assert rejected_offer.merchant_decision == "REJECT"

    # Verify ApprovalRequest status is updated to REJECTED
    appr = db.query(ApprovalRequest).filter(ApprovalRequest.id == offer.merchant_approval_request_id).first()
    assert appr.status == "REJECTED"


def test_hard_policy_blocks_remain_hard_blocks(db, seed_data):
    """
    Ensure invalid or policy-violating requests are properly rejected upfront:
    1. Quantity <= 0 or > max_quantity
    2. Requested price <= 0
    3. Out of stock
    4. Disabled policy
    """
    # 1. Invalid quantity
    offer_qty = NegotiationEngine.start_negotiation(
        db=db,
        merchant_id="m_merch_test",
        customer_id="user_cust_123",
        product_id="prod_socks_399",
        quantity=10,  # policy.max_quantity is 5
        requested_unit_price=Decimal("350.00")
    )
    assert offer_qty.status == NegotiationState.REJECTED.value
    assert "exceeds maximum allowed quantity limit" in offer_qty.merchant_message

    # 2. Negative/Zero price
    offer_zero = NegotiationEngine.start_negotiation(
        db=db,
        merchant_id="m_merch_test",
        customer_id="user_cust_123",
        product_id="prod_socks_399",
        quantity=1,
        requested_unit_price=Decimal("0.00")
    )
    assert offer_zero.status == NegotiationState.REJECTED.value
    assert "greater than zero" in offer_zero.merchant_message

    # 3. Out of stock
    inv = db.query(Inventory).filter(Inventory.product_id == "prod_socks_399").first()
    inv.stock_quantity = 0
    db.commit()

    offer_stock = NegotiationEngine.start_negotiation(
        db=db,
        merchant_id="m_merch_test",
        customer_id="user_cust_123",
        product_id="prod_socks_399",
        quantity=1,
        requested_unit_price=Decimal("350.00")
    )
    assert offer_stock.status == NegotiationState.REJECTED.value
    assert "Insufficient inventory" in offer_stock.merchant_message

    # Reset stock
    inv.stock_quantity = 50
    db.commit()

    # 4. Policy disabled
    pol = db.query(MerchantNegotiationPolicy).filter(MerchantNegotiationPolicy.merchant_id == "m_merch_test").first()
    pol.enabled = False
    db.commit()

    offer_disabled = NegotiationEngine.start_negotiation(
        db=db,
        merchant_id="m_merch_test",
        customer_id="user_cust_123",
        product_id="prod_socks_399",
        quantity=1,
        requested_unit_price=Decimal("350.00")
    )
    assert offer_disabled.status == NegotiationState.REJECTED.value
    assert "currently disabled" in offer_disabled.merchant_message


def test_customer_authorization_and_server_authoritative_pricing(db, seed_data):
    """
    Test customer authorization security:
    - Customer A's offer cannot be accepted/modified by Customer B.
    - List price is strictly authoritative from DB product record.
    """
    offer = NegotiationEngine.start_negotiation(
        db=db,
        merchant_id="m_merch_test",
        customer_id="user_cust_123",
        product_id="prod_socks_399",
        quantity=1,
        requested_unit_price=Decimal("200.00")
    )

    # Approve offer so customer can accept
    NegotiationEngine.merchant_approve_offer(
        db=db,
        offer_id=offer.id,
        merchant_id="m_merch_test",
        admin_user_id="user_merch_123"
    )

    # Customer B tries to accept Customer A's offer -> Should fail
    with pytest.raises(ValueError, match="Customer mismatch"):
        NegotiationEngine.customer_accept_offer(
            db=db,
            offer_id=offer.id,
            customer_id="user_cust_456"
        )

    # Customer A accepts their own offer -> Succeeds
    accepted_offer = NegotiationEngine.customer_accept_offer(
        db=db,
        offer_id=offer.id,
        customer_id="user_cust_123"
    )
    assert accepted_offer.status == NegotiationState.CUSTOMER_ACCEPTED.value
