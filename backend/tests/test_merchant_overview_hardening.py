import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database.session import SessionLocal
from app.database.models.merchant import Merchant
from app.database.models.user import User
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.purchase_intent import PurchaseIntent
from app.database.models.payment_transaction import PaymentTransaction
from app.database.models.recommendation import Recommendation
from app.database.models.audit_event import AuditEvent
from app.database.models.base import generate_uuid
from app.agents.merchant_revenue_agent import MerchantRevenueAgent

client = TestClient(app)

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()

from app.services.audit_service import AuditService
from app.database.models.transaction_authorization import TransactionAuthorization

def test_overview_metrics_authoritative_source_consistency(db_session: Session):
    """Verifies that all 6 overview metrics are grounded in authoritative SQL models with zero fabricated data."""
    merchant = db_session.query(Merchant).first()
    assert merchant is not None, "Merchant must exist"
    
    # 1. Products / Active Catalog
    db_prods_count = db_session.query(Product).filter(Product.merchant_id == merchant.id, Product.is_active == True).count()
    prod_res = client.get(f"/api/v1/products/?merchant_id={merchant.id}&limit={max(2000, db_prods_count)}")
    assert prod_res.status_code == 200
    products = prod_res.json()
    assert len(products) == db_prods_count

    # 2. Purchase Intents
    pi_res = client.get(f"/api/v1/purchase-intents/?merchant_id={merchant.id}")
    assert pi_res.status_code == 200
    intents = pi_res.json()
    db_intents_count = db_session.query(PurchaseIntent).filter(PurchaseIntent.merchant_id == merchant.id).count()
    assert len(intents) == db_intents_count

    # 3. AI Commerce Activity
    ai_act_res = client.get(f"/api/v1/ai-commerce/activity?merchant_id={merchant.id}")
    assert ai_act_res.status_code == 200
    ai_act = ai_act_res.json()
    assert "active_agent_requests" in ai_act
    assert "completed_orders_count" in ai_act
    assert "total_ai_revenue" in ai_act
    assert isinstance(ai_act["recent_events"], list)

    # 4. Recommendation Stats / AI Cross-Sell Rate
    rec_res = client.get(f"/api/v1/ai/recommendations/stats/summary?merchant_id={merchant.id}")
    assert rec_res.status_code == 200
    rec_stats = rec_res.json()
    assert "total_recommendations" in rec_stats
    assert "accepted_count" in rec_stats
    assert "acceptance_rate" in rec_stats
    assert "additional_cart_value" in rec_stats

    # 5. Revenue Metrics
    rev_res = client.get(f"/api/v1/revenue/metrics?merchant_id={merchant.id}")
    assert rev_res.status_code == 200
    rev_metrics = rev_res.json()
    assert "total_opportunities" in rev_metrics
    assert "projected_incremental_gmv" in rev_metrics

def test_ai_attributed_gmv_strictly_completed_payments(db_session: Session):
    """Ensures AI attributed GMV only counts COMPLETED payment transactions."""
    m_id = f"m_test_gmv_{generate_uuid()[:8]}"
    merchant = Merchant(id=m_id, name="GMV Audit Merchant", domain=f"{m_id}.test")
    db_session.add(merchant)
    db_session.commit()

    # Create dummy purchase intent & auth for foreign key constraints
    pi = PurchaseIntent(
        id=f"pi_{generate_uuid()[:8]}",
        merchant_id=m_id,
        buyer_id="buyer_test_1",
        session_id="sess_test_1",
        cart_id="cart_test_1",
        requested_amount=Decimal("5000.00"),
        status="AUTHORIZED"
    )
    auth = TransactionAuthorization(
        id=f"auth_{generate_uuid()[:8]}",
        policy_evaluation_id=f"pe_{generate_uuid()[:8]}",
        policy_version="1.0",
        purchase_intent_id=pi.id,
        merchant_id=m_id,
        authorized_amount=Decimal("5000.00"),
        authorized_by="POLICY_ENGINE",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        status="AUTHORIZED"
    )
    db_session.add_all([pi, auth])
    db_session.commit()

    # Add 1 COMPLETED transaction of 5,000 and 1 PENDING transaction of 10,000
    tx1 = PaymentTransaction(
        id=f"tx_{generate_uuid()[:8]}",
        purchase_intent_id=pi.id,
        authorization_id=auth.id,
        merchant_id=m_id,
        amount=Decimal("5000.00"),
        currency="INR",
        status="COMPLETED",
        idempotency_key=f"idemp_{generate_uuid()[:8]}",
        receipt="rcpt_1"
    )
    tx2 = PaymentTransaction(
        id=f"tx_{generate_uuid()[:8]}",
        purchase_intent_id=pi.id,
        authorization_id=auth.id,
        merchant_id=m_id,
        amount=Decimal("10000.00"),
        currency="INR",
        status="PENDING",
        idempotency_key=f"idemp_{generate_uuid()[:8]}",
        receipt="rcpt_2"
    )
    db_session.add_all([tx1, tx2])
    db_session.commit()

    ai_act_res = client.get(f"/api/v1/ai-commerce/activity?merchant_id={m_id}")
    assert ai_act_res.status_code == 200
    data = ai_act_res.json()
    # Must only count COMPLETED transaction (5000), ignoring PENDING (10000)
    assert data["total_ai_revenue"] == 5000.0
    assert data["completed_orders_count"] == 1

def test_cross_sell_acceptance_rate_deterministic_semantics(db_session: Session):
    """Verifies that acceptance rate accurately calculates accepted / total * 100 without distortion."""
    m_id = f"m_test_cross_{generate_uuid()[:8]}"
    merchant = Merchant(id=m_id, name="Cross Sell Audit Merchant", domain=f"{m_id}.test")
    db_session.add(merchant)
    db_session.commit()

    p = Product(id=f"prod_{generate_uuid()[:8]}", merchant_id=m_id, name="Audit Shoe", category="Running", price=Decimal("1000.00"), is_active=True)
    db_session.add(p)
    db_session.commit()

    # 1 ACCEPTED, 1 REJECTED recommendation
    r1 = Recommendation(
        id=f"rec_{generate_uuid()[:8]}",
        merchant_id=m_id,
        session_id="sess_1",
        type="CROSS_SELL",
        recommended_product_id=p.id,
        reason="Complementary basket match",
        confidence=0.85,
        status="ACCEPTED"
    )
    r2 = Recommendation(
        id=f"rec_{generate_uuid()[:8]}",
        merchant_id=m_id,
        session_id="sess_2",
        type="CROSS_SELL",
        recommended_product_id=p.id,
        reason="Complementary basket match",
        confidence=0.80,
        status="REJECTED"
    )
    db_session.add_all([r1, r2])
    db_session.commit()

    rec_res = client.get(f"/api/v1/ai/recommendations/stats/summary?merchant_id={m_id}")
    assert rec_res.status_code == 200
    stats = rec_res.json()
    assert stats["total_recommendations"] == 2
    assert stats["accepted_count"] == 1
    assert stats["rejected_count"] == 1
    assert stats["acceptance_rate"] == 50.0  # 1 / 2 * 100
    assert float(stats["additional_cart_value"]) == 1000.0

def test_tenant_isolation_in_activity_and_stats(db_session: Session):
    """Ensures Merchant A cannot see Merchant B's activity events or recommendation statistics."""
    mA_id = f"mA_{generate_uuid()[:8]}"
    mB_id = f"mB_{generate_uuid()[:8]}"
    mA = Merchant(id=mA_id, name="Merchant A", domain=f"{mA_id}.test")
    mB = Merchant(id=mB_id, name="Merchant B", domain=f"{mB_id}.test")
    db_session.add_all([mA, mB])
    db_session.commit()

    # AuditEvent for Merchant A using AuditService
    AuditService.record_event(
        db=db_session,
        merchant_id=mA_id,
        trace_id=f"trc_{generate_uuid()[:8]}",
        actor_type="BUYER_AGENT",
        action="AI_BUYER_REQUESTED",
        event_type="AI_BUYER_REQUESTED",
        status="SUCCESS",
        metadata_json={"query": "marathon shoes"}
    )
    db_session.commit()

    # Merchant B querying activity must have 0 events for Merchant A
    ai_act_B = client.get(f"/api/v1/ai-commerce/activity?merchant_id={mB_id}").json()
    assert ai_act_B["active_agent_requests"] == 0
    assert len(ai_act_B["recent_events"]) == 0

    # Merchant A querying activity gets 1 event
    ai_act_A = client.get(f"/api/v1/ai-commerce/activity?merchant_id={mA_id}").json()
    assert ai_act_A["active_agent_requests"] == 1
    assert len(ai_act_A["recent_events"]) == 1

def test_distinct_buyer_ai_vs_merchant_revenue_agent_operations(db_session: Session):
    """Verifies that Buyer Agent search handles shopper requests while MerchantRevenueAgent processes merchant queries."""
    merchant = db_session.query(Merchant).first()
    
    # 1. Buyer Agent Search
    buyer_res = client.post("/api/v1/ai-commerce/search", json={
        "protocol_version": "1.0",
        "request_id": "req_audit_1",
        "natural_language_query": "I need marathon running shoes under ₹5,000."
    })
    assert buyer_res.status_code == 200
    b_data = buyer_res.json()
    assert "offers" in b_data
    assert "session_id" in b_data

    # 2. Merchant Revenue Agent Query
    agent = MerchantRevenueAgent(db=db_session, merchant_id=merchant.id)
    m_resp = agent.process_query("What are my best cross sell opportunities?")
    assert m_resp.top_human_view is not None
    assert m_resp.top_agent_view is not None
    assert m_resp.intent_detected in ["CROSS_SELL", "GROWTH_OVERVIEW", "DISCOUNT_SIMULATION", "INVENTORY_CLEARANCE"]


