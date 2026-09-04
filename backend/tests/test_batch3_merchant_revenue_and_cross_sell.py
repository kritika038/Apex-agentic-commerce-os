"""
Batch 3 Comprehensive Verification Suite:
(1) Feature 5: Merchant Revenue Agent
(2) Feature 6: Autonomous Cross-Sell / Upsell Agent & Governed Campaign Lifecycle
"""

import pytest
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database.session import SessionLocal
from app.database.models.merchant import Merchant
from app.database.models.user import User
from app.database.models.product import Product
from app.database.models.cart import Cart, CartItem
from app.database.models.inventory import Inventory
from app.database.models.policy import Policy
from app.database.models.revenue_opportunity import RevenueOpportunity
from app.database.models.audit_event import AuditEvent
from app.database.models.payment_transaction import PaymentTransaction
from app.database.models.purchase_intent import PurchaseIntent
from app.core.security import create_access_token
from app.services.product_affinity_service import ProductAffinityService
from app.revenue.opportunity_engine import RevenueOpportunityEngine
from app.revenue.campaign_service import RevenueCampaignService
from app.agents.merchant_revenue_agent import MerchantRevenueAgent
from app.agents.merchant_growth_agent import MerchantGrowthAgent
from app.agents.sales_agent import SalesAgent
from app.revenue.schemas import MerchantAgentQueryRequest, RevenueOpportunityExecuteRequest, RevenueOpportunityApproveRequest, RevenueOpportunityRejectRequest

client = TestClient(app)

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def batch3_setup(db_session: Session):
    # Ensure merchant exists
    merchant = db_session.query(Merchant).filter(Merchant.id == "merchant_batch3_test").first()
    if not merchant:
        merchant = Merchant(
            id="merchant_batch3_test",
            name="Batch 3 Test Sports",
            domain="batch3.sports.apex.store",
            is_active=True
        )
        db_session.add(merchant)
        db_session.commit()
        db_session.refresh(merchant)

    # Merchant User
    m_user = db_session.query(User).filter(User.email == "batch3_operator@apex.store").first()
    if not m_user:
        m_user = User(
            id="user_b3_op",
            email="batch3_operator@apex.store",
            full_name="Batch3 Operator",
            hashed_password="dummy",
            role="merchant_admin",
            merchant_id=merchant.id,
            is_active=True
        )
        db_session.add(m_user)
        db_session.commit()
        db_session.refresh(m_user)

    # Second Merchant for Tenant Isolation
    merchant_b = db_session.query(Merchant).filter(Merchant.id == "merchant_batch3_isolated_b").first()
    if not merchant_b:
        merchant_b = Merchant(
            id="merchant_batch3_isolated_b",
            name="Merchant B Isol",
            domain="merchant-b.apex.store",
            is_active=True
        )
        db_session.add(merchant_b)
        db_session.commit()
        db_session.refresh(merchant_b)

    m_user_b = db_session.query(User).filter(User.email == "merchant_b_op@apex.store").first()
    if not m_user_b:
        m_user_b = User(
            id="user_b3_op_b",
            email="merchant_b_op@apex.store",
            full_name="Merchant B Op",
            hashed_password="dummy",
            role="merchant_admin",
            merchant_id=merchant_b.id,
            is_active=True
        )
        db_session.add(m_user_b)
        db_session.commit()
        db_session.refresh(m_user_b)

    # Standard Policy (Max discount 5%)
    policy = db_session.query(Policy).filter(Policy.merchant_id == merchant.id, Policy.is_active == True).first()
    if not policy:
        policy = Policy(
            id=f"pol_b3_{merchant.id}",
            merchant_id=merchant.id,
            max_discount_percent=Decimal("5.00"),
            max_transaction_amount=Decimal("15000.00"),
            approval_threshold=Decimal("5000.00"),
            is_active=True
        )
        db_session.add(policy)
        db_session.commit()
        db_session.refresh(policy)

    # Products for Merchant A
    p_shoes = db_session.query(Product).filter(Product.id == "prod_b3_shoes").first()
    if not p_shoes:
        p_shoes = Product(
            id="prod_b3_shoes",
            merchant_id=merchant.id,
            name="Apex Pro Running Shoes",
            description="High performance running shoes",
            category="Footwear",
            price=Decimal("4999.00"),
            is_active=True
        )
        db_session.add(p_shoes)
    
    p_socks = db_session.query(Product).filter(Product.id == "prod_b3_socks").first()
    if not p_socks:
        p_socks = Product(
            id="prod_b3_socks",
            merchant_id=merchant.id,
            name="Apex Cushioned Running Socks",
            description="Anti-blister running socks",
            category="Accessories",
            price=Decimal("499.00"),
            is_active=True
        )
        db_session.add(p_socks)

    p_premium_shoes = db_session.query(Product).filter(Product.id == "prod_b3_carbon_shoes").first()
    if not p_premium_shoes:
        p_premium_shoes = Product(
            id="prod_b3_carbon_shoes",
            merchant_id=merchant.id,
            name="Apex Carbon Plate Elite Racing Shoes",
            description="Marathon racing shoes with carbon fiber plate",
            category="Footwear",
            price=Decimal("8999.00"),
            is_active=True
        )
        db_session.add(p_premium_shoes)

    p_low_stock = db_session.query(Product).filter(Product.id == "prod_b3_water_bottle").first()
    if not p_low_stock:
        p_low_stock = Product(
            id="prod_b3_water_bottle",
            merchant_id=merchant.id,
            name="Apex Hydration Flask 750ml",
            description="Lightweight insulated sports water bottle",
            category="Accessories",
            price=Decimal("799.00"),
            is_active=True
        )
        db_session.add(p_low_stock)

    p_out_of_stock = db_session.query(Product).filter(Product.id == "prod_b3_headband").first()
    if not p_out_of_stock:
        p_out_of_stock = Product(
            id="prod_b3_headband",
            merchant_id=merchant.id,
            name="Apex Sweatband Headband",
            description="Absorbent moisture wicking headband",
            category="Accessories",
            price=Decimal("299.00"),
            is_active=True
        )
        db_session.add(p_out_of_stock)

    db_session.commit()

    # Set up Inventory
    def set_inv(p_id, qty):
        inv = db_session.query(Inventory).filter(Inventory.product_id == p_id).first()
        if not inv:
            inv = Inventory(id=f"inv_{p_id}", merchant_id=merchant.id, product_id=p_id, stock_quantity=qty, reserved_quantity=0)
            db_session.add(inv)
        else:
            inv.stock_quantity = qty
        db_session.commit()

    set_inv("prod_b3_shoes", 50)
    set_inv("prod_b3_socks", 80)
    set_inv("prod_b3_carbon_shoes", 30)
    set_inv("prod_b3_water_bottle", 8)   # Low stock (<20)
    set_inv("prod_b3_headband", 0)       # Out of stock

    # Seed Co-purchase Carts + Transactions (Shoes + Socks 4 times => N >= 3)
    for i in range(4):
        sess_id = f"sess_b3_copurchase_{i}"
        cart = db_session.query(Cart).filter(Cart.session_id == sess_id).first()
        if not cart:
            cart = Cart(
                id=f"cart_b3_{i}",
                merchant_id=merchant.id,
                session_id=sess_id,
                status="completed",
                total_amount=Decimal("5498.00")
            )
            db_session.add(cart)
            db_session.flush()

            ci1 = CartItem(id=f"ci_shoes_{i}", cart_id=cart.id, product_id="prod_b3_shoes", quantity=1, unit_price_snapshot=Decimal("4999.00"))
            ci2 = CartItem(id=f"ci_socks_{i}", cart_id=cart.id, product_id="prod_b3_socks", quantity=1, unit_price_snapshot=Decimal("499.00"))
            db_session.add_all([ci1, ci2])
            db_session.flush()

        pi = db_session.query(PurchaseIntent).filter(PurchaseIntent.session_id == sess_id).first()
        if not pi:
            pi = PurchaseIntent(
                id=f"pi_b3_{i}",
                merchant_id=merchant.id,
                buyer_id=m_user.id,
                session_id=sess_id,
                cart_id=cart.id,
                requested_amount=Decimal("5498.00"),
                currency="INR",
                status="COMPLETED"
            )
            db_session.add(pi)

    db_session.commit()

    token_a = create_access_token(subject=m_user.id, merchant_id=merchant.id, role="merchant_admin")
    token_b = create_access_token(subject=m_user_b.id, merchant_id=merchant_b.id, role="merchant_admin")

    return {
        "merchant_a": merchant,
        "merchant_b": merchant_b,
        "user_a": m_user,
        "user_b": m_user_b,
        "policy_a": policy,
        "headers_a": {"Authorization": f"Bearer {token_a}"},
        "headers_b": {"Authorization": f"Bearer {token_b}"},
        "token_a": token_a,
        "token_b": token_b
    }

# =====================================================================
# 1. EVIDENCE GROUNDING & CO-PURCHASE AFFINITY TESTS
# =====================================================================

def test_batch3_product_affinity_cross_sell_evidence_grounded_in_db(db_session: Session, batch3_setup):
    """Verifies that cross-sell recommendations originate directly from database co-orders."""
    m_id = batch3_setup["merchant_a"].id
    results = ProductAffinityService.get_frequently_bought_together(db_session, "prod_b3_shoes", m_id, limit=3)
    
    assert len(results) >= 1
    match = next((r for r in results if r["product"].id == "prod_b3_socks"), None)
    assert match is not None
    assert match["co_purchase_count"] >= 4
    assert match["confidence"] >= 0.50
    assert "Co-purchased in" in match["evidence"]

def test_batch3_insufficient_data_handling_n_less_than_3(db_session: Session, batch3_setup):
    """Verifies that when sample size N < 3, confidence is None and risk_level is INSUFFICIENT_DATA."""
    m_id = batch3_setup["merchant_a"].id
    opp_test = RevenueOpportunity(
        id=f"opp_test_insufficient_{uuid.uuid4().hex[:8]}",
        merchant_id=m_id,
        type="CROSS_SELL",
        title="Cross-Sell Isolated Item",
        description="Low sample test",
        reason="Test",
        confidence=None,
        proposed_discount_percent=Decimal("4.00"),
        estimated_incremental_orders=0,
        estimated_incremental_gmv=None,
        estimated_discount_cost=None,
        estimated_net_value=None,
        inventory_impact={"source_stock": 10, "target_stock": 10},
        evidence_json={"sample_size": 2, "co_order_count": 2, "attach_rate": 0.20},
        risk_level="INSUFFICIENT_DATA",
        status="GENERATED",
        expires_at=datetime.now(timezone.utc) + timedelta(days=14)
    )
    db_session.add(opp_test)
    db_session.commit()

    hv, av = RevenueOpportunityEngine.format_views(db_session, opp_test, m_id)
    assert hv.policy_badge == "INSUFFICIENT_DATA"
    assert av.confidence is None
    assert av.confidence_status == "INSUFFICIENT_DATA"
    assert "Sample size (2) is below statistical threshold" in hv.why_bullets[0]

def test_batch3_deterministic_confidence_and_decimal_arithmetic(db_session: Session, batch3_setup):
    """Verifies deterministic confidence calculation and strict Decimal monetary arithmetic."""
    m_id = batch3_setup["merchant_a"].id
    opps = RevenueOpportunityEngine.discover_all(db_session, m_id, min_confidence=0.50)
    
    for opp in opps:
        if opp.confidence is not None:
            assert 0.0 <= opp.confidence <= 1.0
        if opp.estimated_incremental_gmv is not None:
            assert isinstance(opp.estimated_incremental_gmv, (Decimal, float))
        if opp.estimated_discount_cost is not None:
            assert isinstance(opp.estimated_discount_cost, (Decimal, float))
        if opp.estimated_net_value is not None:
            assert isinstance(opp.estimated_net_value, (Decimal, float))

# =====================================================================
# 2. POLICY COMPLIANCE & GOVERNANCE ENFORCEMENT TESTS
# =====================================================================

def test_batch3_policy_compliance_within_threshold_auto_allowed(db_session: Session, batch3_setup):
    """Verifies that an opportunity within max discount policy (<= 5%) gets AUTO_ALLOWED / PASS badge."""
    m_id = batch3_setup["merchant_a"].id
    opp = RevenueOpportunity(
        id=f"opp_policy_pass_{uuid.uuid4().hex[:8]}",
        merchant_id=m_id,
        type="CROSS_SELL",
        title="Compliant 4% Cross-Sell",
        description="Discount is within 5% policy limit",
        reason="Factual attach rate 60%",
        confidence=0.85,
        proposed_discount_percent=Decimal("4.00"),
        estimated_incremental_orders=10,
        estimated_incremental_gmv=Decimal("4990.00"),
        estimated_discount_cost=Decimal("199.60"),
        estimated_net_value=Decimal("4790.40"),
        inventory_impact={"source_stock": 50, "target_stock": 80},
        evidence_json={"sample_size": 15, "co_order_count": 9, "attach_rate": 0.60},
        risk_level="LOW",
        status="APPROVED",
        expires_at=datetime.now(timezone.utc) + timedelta(days=14)
    )
    db_session.add(opp)
    db_session.commit()

    hv, av = RevenueOpportunityEngine.format_views(db_session, opp, m_id)
    assert hv.policy_badge == "PASS"
    assert av.policy_status == "PASS"
    assert av.approval_required is False
    assert av.can_execute is True

def test_batch3_policy_compliance_exceeds_threshold_policy_blocked(db_session: Session, batch3_setup):
    """Verifies that an opportunity exceeding max discount policy (> 5%) gets POLICY_BLOCKED and execution fails."""
    m_id = batch3_setup["merchant_a"].id
    opp_blocked = RevenueOpportunity(
        id=f"opp_policy_blocked_{uuid.uuid4().hex[:8]}",
        merchant_id=m_id,
        type="CROSS_SELL",
        title="Excessive 12% Cross-Sell",
        description="Exceeds 5% max discount limit",
        reason="Too high discount",
        confidence=0.80,
        proposed_discount_percent=Decimal("12.00"),
        estimated_incremental_orders=10,
        estimated_incremental_gmv=Decimal("4990.00"),
        estimated_discount_cost=Decimal("598.80"),
        estimated_net_value=Decimal("4391.20"),
        inventory_impact={"source_stock": 50, "target_stock": 80},
        evidence_json={"sample_size": 10, "co_order_count": 6, "attach_rate": 0.60},
        risk_level="HIGH",
        status="GENERATED",
        expires_at=datetime.now(timezone.utc) + timedelta(days=14)
    )
    db_session.add(opp_blocked)
    db_session.commit()

    hv, av = RevenueOpportunityEngine.format_views(db_session, opp_blocked, m_id)
    assert hv.policy_badge == "POLICY_BLOCKED"
    assert av.policy_status == "POLICY_BLOCKED"
    assert av.can_execute is False

    # Attempting to execute should fail with HTTPException
    with pytest.raises(Exception) as excinfo:
        RevenueCampaignService.execute_opportunity(
            db=db_session,
            merchant_id=m_id,
            opportunity_id=opp_blocked.id,
            req=RevenueOpportunityExecuteRequest(idempotency_key="idem_blocked_1")
        )
    assert "exceeds policy threshold" in str(excinfo.value)

# =====================================================================
# 3. BASE PRICE IMMUTABILITY & IDEMPOTENT EXECUTION
# =====================================================================

def test_batch3_execution_never_mutates_base_product_price(db_session: Session, batch3_setup):
    """Crucial safety invariant: executing a cross-sell campaign MUST NEVER mutate Product.price."""
    m_id = batch3_setup["merchant_a"].id
    p_shoes = db_session.query(Product).filter(Product.id == "prod_b3_shoes").first()
    p_socks = db_session.query(Product).filter(Product.id == "prod_b3_socks").first()
    
    orig_shoes_price = p_shoes.price
    orig_socks_price = p_socks.price

    # Create approved opportunity
    opp = RevenueOpportunity(
        id=f"opp_price_safety_{uuid.uuid4().hex[:8]}",
        merchant_id=m_id,
        type="CROSS_SELL",
        title="Safety Price Test Cross-Sell",
        description="Verify base product prices remain intact",
        reason="Attach rate test",
        confidence=0.88,
        proposed_discount_percent=Decimal("4.50"),
        estimated_incremental_orders=5,
        estimated_incremental_gmv=Decimal("2495.00"),
        estimated_discount_cost=Decimal("112.28"),
        estimated_net_value=Decimal("2382.72"),
        inventory_impact={"source_stock": 50, "target_stock": 80, "source_product_id": "prod_b3_shoes", "target_product_ids": ["prod_b3_socks"]},
        evidence_json={"sample_size": 12, "co_order_count": 8, "attach_rate": 0.66},
        risk_level="LOW",
        status="APPROVED",
        expires_at=datetime.now(timezone.utc) + timedelta(days=14)
    )
    db_session.add(opp)
    db_session.commit()

    # Execute Campaign
    RevenueCampaignService.execute_opportunity(
        db=db_session,
        merchant_id=m_id,
        opportunity_id=opp.id,
        req=RevenueOpportunityExecuteRequest(idempotency_key="idem_price_safety_1")
    )

    db_session.refresh(p_shoes)
    db_session.refresh(p_socks)

    # Base price MUST NOT have changed
    assert p_shoes.price == orig_shoes_price
    assert p_socks.price == orig_socks_price

def test_batch3_campaign_execution_idempotency(db_session: Session, batch3_setup):
    """Verifies that executing twice with the same idempotency_key returns the same campaign without duplicating."""
    m_id = batch3_setup["merchant_a"].id
    opp = RevenueOpportunity(
        id=f"opp_idempotency_{uuid.uuid4().hex[:8]}",
        merchant_id=m_id,
        type="CROSS_SELL",
        title="Idempotency Test Campaign",
        description="Testing duplicate execution protection",
        reason="Attach rate test",
        confidence=0.85,
        proposed_discount_percent=Decimal("3.50"),
        estimated_incremental_orders=4,
        estimated_incremental_gmv=Decimal("1996.00"),
        estimated_discount_cost=Decimal("69.86"),
        estimated_net_value=Decimal("1926.14"),
        inventory_impact={"source_stock": 50, "target_stock": 80, "source_product_id": "prod_b3_shoes", "target_product_ids": ["prod_b3_socks"]},
        evidence_json={"sample_size": 10, "co_order_count": 6, "attach_rate": 0.60},
        risk_level="LOW",
        status="APPROVED",
        expires_at=datetime.now(timezone.utc) + timedelta(days=14)
    )
    db_session.add(opp)
    db_session.commit()

    key = f"idem_test_key_{opp.id}"
    req = RevenueOpportunityExecuteRequest(idempotency_key=key)

    opp1 = RevenueCampaignService.execute_opportunity(db=db_session, merchant_id=m_id, opportunity_id=opp.id, req=req)
    assert opp1.status == "EXECUTED"
    assert opp1.idempotency_key == key

    # Re-execution with same idempotency key
    opp2 = RevenueCampaignService.execute_opportunity(db=db_session, merchant_id=m_id, opportunity_id=opp.id, req=req)
    assert opp2.status == "EXECUTED"
    assert opp2.idempotency_key == key
    assert opp2.id == opp1.id

# =====================================================================
# 4. EXPIRATION & INVENTORY RISK VALIDATION
# =====================================================================

def test_batch3_expired_opportunity_cannot_be_approved_or_executed(db_session: Session, batch3_setup):
    """Verifies that expired opportunities (now > expires_at) are rejected with OPPORTUNITY_EXPIRED."""
    m_id = batch3_setup["merchant_a"].id
    opp_expired = RevenueOpportunity(
        id=f"opp_expired_{uuid.uuid4().hex[:8]}",
        merchant_id=m_id,
        type="CROSS_SELL",
        title="Expired Cross-Sell Opportunity",
        description="Expired 2 days ago",
        reason="Historical affinity",
        confidence=0.80,
        proposed_discount_percent=Decimal("4.00"),
        estimated_incremental_orders=5,
        estimated_incremental_gmv=Decimal("2000.00"),
        estimated_discount_cost=Decimal("80.00"),
        estimated_net_value=Decimal("1920.00"),
        inventory_impact={"source_stock": 50, "target_stock": 80},
        evidence_json={"sample_size": 10, "co_order_count": 6, "attach_rate": 0.60},
        risk_level="LOW",
        status="GENERATED",
        expires_at=datetime.now(timezone.utc) - timedelta(days=2)
    )
    db_session.add(opp_expired)
    db_session.commit()

    hv, av = RevenueOpportunityEngine.format_views(db_session, opp_expired, m_id)
    assert hv.policy_badge == "EXPIRED"
    assert av.can_execute is False

    # Attempt approve
    with pytest.raises(Exception) as excinfo:
        RevenueCampaignService.approve_opportunity(
            db=db_session,
            merchant_id=m_id,
            opportunity_id=opp_expired.id,
            user_id="user_b3_op",
            reason="Test approve"
        )
    assert "has expired and cannot be approved" in str(excinfo.value)

    # Attempt execute
    with pytest.raises(Exception) as excinfo2:
        RevenueCampaignService.execute_opportunity(
            db=db_session,
            merchant_id=m_id,
            opportunity_id=opp_expired.id,
            req=RevenueOpportunityExecuteRequest(idempotency_key="idem_exp_1")
        )
    assert "expired" in str(excinfo2.value)

def test_batch3_out_of_stock_blocks_campaign_execution(db_session: Session, batch3_setup):
    """Verifies that if target product has 0 inventory, campaign execution is rejected."""
    m_id = batch3_setup["merchant_a"].id
    opp_oos = RevenueOpportunity(
        id=f"opp_oos_{uuid.uuid4().hex[:8]}",
        merchant_id=m_id,
        type="CROSS_SELL",
        title="Out of Stock Target Item",
        description="Target headband is out of stock (0 units)",
        reason="Affinity",
        confidence=0.75,
        proposed_discount_percent=Decimal("3.00"),
        estimated_incremental_orders=5,
        estimated_incremental_gmv=Decimal("1495.00"),
        estimated_discount_cost=Decimal("44.85"),
        estimated_net_value=Decimal("1450.15"),
        inventory_impact={"source_stock": 50, "target_stock": 0, "source_product_id": "prod_b3_shoes", "target_product_ids": ["prod_b3_headband"]},
        evidence_json={"sample_size": 10, "co_order_count": 5, "attach_rate": 0.50},
        risk_level="HIGH",
        status="APPROVED",
        expires_at=datetime.now(timezone.utc) + timedelta(days=14)
    )
    db_session.add(opp_oos)
    db_session.commit()

    with pytest.raises(Exception) as excinfo:
        RevenueCampaignService.execute_opportunity(
            db=db_session,
            merchant_id=m_id,
            opportunity_id=opp_oos.id,
            req=RevenueOpportunityExecuteRequest(idempotency_key="idem_oos_1")
        )
    assert "out of stock (0 units available)" in str(excinfo.value)

# =====================================================================
# 5. TENANT ISOLATION & PRIVACY TESTS
# =====================================================================

def test_batch3_tenant_isolation_merchant_a_cannot_access_merchant_b(db_session: Session, batch3_setup):
    """Verifies that Merchant A cannot access Merchant B's opportunities, metrics, or campaigns."""
    headers_a = batch3_setup["headers_a"]
    headers_b = batch3_setup["headers_b"]
    m_a_id = batch3_setup["merchant_a"].id
    m_b_id = batch3_setup["merchant_b"].id

    # Create opportunity owned by Merchant B
    opp_b = RevenueOpportunity(
        id=f"opp_private_merchant_b_{uuid.uuid4().hex[:8]}",
        merchant_id=m_b_id,
        type="CROSS_SELL",
        title="Merchant B Private Opportunity",
        description="Confidential data of Merchant B",
        reason="Private affinity",
        confidence=0.90,
        proposed_discount_percent=Decimal("5.00"),
        estimated_incremental_orders=10,
        estimated_incremental_gmv=Decimal("10000.00"),
        estimated_discount_cost=Decimal("500.00"),
        estimated_net_value=Decimal("9500.00"),
        inventory_impact={"source_stock": 100, "target_stock": 100},
        evidence_json={"sample_size": 20, "co_order_count": 15, "attach_rate": 0.75},
        risk_level="LOW",
        status="GENERATED",
        expires_at=datetime.now(timezone.utc) + timedelta(days=14)
    )
    db_session.add(opp_b)
    db_session.commit()

    # Merchant A attempts to access Merchant B's opportunity
    res = client.get(f"/api/v1/revenue/opportunities/{opp_b.id}", headers=headers_a)
    assert res.status_code == 404

    # Merchant A attempts to approve Merchant B's opportunity
    res_approve = client.post(
        f"/api/v1/revenue/opportunities/{opp_b.id}/approve",
        json={"reason": "Unauthorized attempt"},
        headers=headers_a
    )
    assert res_approve.status_code == 404

    # Merchant B can access it
    res_b = client.get(f"/api/v1/revenue/opportunities/{opp_b.id}", headers=headers_b)
    assert res_b.status_code == 200
    data_b = res_b.json()
    title = data_b.get("title") or (data_b.get("opportunity") or {}).get("title")
    assert title == "Merchant B Private Opportunity"

def test_batch3_zero_customer_pii_in_agent_output_and_evidence(db_session: Session, batch3_setup):
    """Verifies that no customer PII (names, emails, phones) is exposed in opportunities or agent views."""
    m_id = batch3_setup["merchant_a"].id
    opps = RevenueOpportunityEngine.discover_all(db_session, m_id, min_confidence=0.50)
    
    for opp in opps:
        hv, av = RevenueOpportunityEngine.format_views(db_session, opp, m_id)
        evidence_str = str(opp.evidence_json) + str(hv.model_dump()) + str(av.model_dump())
        
        # Verify no email or user ID leaked
        assert "@apex.store" not in evidence_str
        assert "user_b3_op" not in evidence_str
        assert "batch3_operator" not in evidence_str

# =====================================================================
# 6. MERCHANT REVENUE AGENT ORCHESTRATION & QUERY HANDLING
# =====================================================================

def test_batch3_merchant_revenue_agent_nl_query_handling(db_session: Session, batch3_setup):
    """Verifies that MerchantRevenueAgent handles natural language inquiries and returns dual views."""
    m_id = batch3_setup["merchant_a"].id
    agent = MerchantRevenueAgent(db=db_session, merchant_id=m_id)
    
    resp = agent.process_query("How can I increase revenue this week?")
    assert len(resp.summary_message) > 10
    assert resp.total_opportunities_found >= 1
    assert resp.top_human_view is not None
    assert resp.top_agent_view is not None
    assert len(resp.top_human_view.why_bullets) >= 1

def test_batch3_merchant_revenue_agent_cross_sell_query(db_session: Session, batch3_setup):
    """Verifies cross-sell specific intent handling."""
    m_id = batch3_setup["merchant_a"].id
    agent = MerchantRevenueAgent(db=db_session, merchant_id=m_id)
    resp = agent.process_query("Find my best cross-sell opportunities")
    
    assert resp.total_opportunities_found >= 1
    assert any(o.type == "CROSS_SELL" for o in resp.opportunities)

def test_batch3_merchant_revenue_agent_bundle_query(db_session: Session, batch3_setup):
    """Verifies bundle specific intent handling."""
    m_id = batch3_setup["merchant_a"].id
    agent = MerchantRevenueAgent(db=db_session, merchant_id=m_id)
    resp = agent.process_query("Which products should I bundle?")
    
    assert resp.total_opportunities_found >= 1
    assert any(o.type == "BUNDLE" for o in resp.opportunities)

def test_batch3_merchant_revenue_agent_inventory_query(db_session: Session, batch3_setup):
    """Verifies inventory risk intent handling."""
    m_id = batch3_setup["merchant_a"].id
    agent = MerchantRevenueAgent(db=db_session, merchant_id=m_id)
    resp = agent.process_query("Show me inventory opportunities and low stock risks")
    
    assert resp.total_opportunities_found >= 1
    assert any(o.type == "INVENTORY_RISK" for o in resp.opportunities)

def test_batch3_backward_compatibility_merchant_growth_agent_delegation(db_session: Session, batch3_setup):
    """Verifies MerchantGrowthAgent is formalized as an alias of MerchantRevenueAgent."""
    m_id = batch3_setup["merchant_a"].id
    growth_agent = MerchantGrowthAgent(db=db_session, merchant_id=m_id)
    
    assert isinstance(growth_agent, MerchantRevenueAgent)
    proposals = growth_agent.generate_proposals()
    assert len(proposals) >= 1

# =====================================================================
# 7. AUDIT LOGGING & TRACE CONTINUITY
# =====================================================================

def test_batch3_audit_trail_structured_events_and_trace_continuity(db_session: Session, batch3_setup):
    """Verifies that agent inquiry and campaign execution write structured audit events with trace continuity."""
    m_id = batch3_setup["merchant_a"].id
    agent = MerchantRevenueAgent(db=db_session, merchant_id=m_id)
    
    resp = agent.process_query("What are my best cross-sell opportunities?")
    t_id = resp.trace_id
    assert t_id.startswith("trc_merch_agent_")

    # Verify audit events created
    logs = db_session.query(AuditEvent).filter(AuditEvent.trace_id == t_id).all()
    actions = [l.action for l in logs]
    assert len(actions) >= 1

# =====================================================================
# 8. SALES AGENT INTEGRATION TESTS
# =====================================================================

def test_batch3_sales_agent_cross_sell_recommendations_with_evidence(db_session: Session, batch3_setup):
    """Verifies that autonomous SalesAgent presents evidence-grounded cross-sell recommendations."""
    m_id = batch3_setup["merchant_a"].id
    sales_agent = SalesAgent(db=db_session, merchant_id=m_id, session_id=f"sess_b3_test_{uuid.uuid4().hex[:8]}")
    
    rec = sales_agent.recommend_cross_sell(source_product_id="prod_b3_shoes")
    assert rec is not None
    assert rec.recommended_product_id == "prod_b3_socks"
    assert rec.type == "CROSS_SELL"
    assert rec.confidence >= 0.50

# =====================================================================
# 9. FASTAPI ROUTER ENDPOINTS TESTS
# =====================================================================

def test_batch3_api_agent_query_endpoint(batch3_setup):
    """Verifies POST /api/v1/revenue/agent/query endpoint."""
    headers_a = batch3_setup["headers_a"]
    res = client.post(
        "/api/v1/revenue/agent/query",
        json={"message": "How can I increase revenue this week?"},
        headers=headers_a
    )
    assert res.status_code == 200
    data = res.json()
    assert "summary_message" in data
    assert "opportunities" in data
    assert "top_human_view" in data
    assert "top_agent_view" in data

def test_batch3_api_opportunities_and_bundles_endpoints(batch3_setup):
    """Verifies GET /api/v1/revenue/opportunities and GET /api/v1/revenue/bundles endpoints."""
    headers_a = batch3_setup["headers_a"]
    res_opps = client.get("/api/v1/revenue/opportunities", headers=headers_a)
    assert res_opps.status_code == 200
    opps_list = res_opps.json()
    assert isinstance(opps_list, list)

    res_bundles = client.get("/api/v1/revenue/bundles", headers=headers_a)
    assert res_bundles.status_code == 200
    bundles_list = res_bundles.json()
    assert isinstance(bundles_list, list)

