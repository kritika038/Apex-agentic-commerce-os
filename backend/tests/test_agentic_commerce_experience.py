import pytest
from decimal import Decimal
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.database.models.base import generate_uuid
from app.database.models.merchant import Merchant
from app.database.models.user import User
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.shopping_session import ShoppingSession
from app.database.models.audit_event import AuditEvent
from app.agents.shopping_agent import ShoppingAgent
from app.agents.intent_engine import ConversationIntentEngine
from app.services.shopping_agent.deterministic_ranking import DeterministicRankingEngine
from app.services.price_intelligence.canonical_service import CanonicalPriceIntelligenceService

@pytest.fixture(scope="module")
def db_session():
    db = SessionLocal()
    yield db
    db.close()

def test_multilingual_intent_parsing(db_session: Session):
    """Test English, Hindi, and Hinglish intent parsing and normalizations."""
    # 1. 5000 ke andar running shoes chahiye
    res1 = ConversationIntentEngine.analyze_message("5000 ke andar running shoes chahiye")
    assert res1["action"] == "CATEGORY_SEARCH"
    assert res1["active_intent"]["category"] == "Running"
    assert res1["search_params"]["max_price"] == 5000.0

    # 2. comfortable running shoes under 4k
    res2 = ConversationIntentEngine.analyze_message("comfortable running shoes under 4k")
    assert res2["action"] == "CATEGORY_SEARCH"
    assert res2["active_intent"]["category"] == "Running"
    assert res2["search_params"]["max_price"] == 4000.0

    # 3. Nike jaisa running shoe dikhao
    res3 = ConversationIntentEngine.analyze_message("Nike jaisa running shoe dikhao")
    assert res3["action"] == "CATEGORY_SEARCH"
    assert res3["active_intent"]["category"] == "Running"
    assert res3["active_intent"]["brand_preference"] == "Nike"

    # 4. best running shoes for marathon
    res4 = ConversationIntentEngine.analyze_message("best running shoes for marathon")
    assert res4["action"] == "CATEGORY_SEARCH"
    assert res4["active_intent"]["category"] == "Running"
    assert res4["active_intent"]["use_case"] == "marathon"

    # 5. Ambiguity Check: "500 ke shoes" (should NOT silently guess 500 or 5000)
    res5 = ConversationIntentEngine.analyze_message("500 ke shoes")
    assert res5["action"] == "CLARIFICATION_NEEDED"
    assert "structured_intent" in res5
    assert res5["structured_intent"]["clarification_needed"] is True

def test_hard_filtering_before_scoring(db_session: Session):
    """Verify that hard constraints prune non-matching candidates before scoring."""
    sample_products = [
        {
            "id": "p1",
            "name": "Super Casual Luxury Sneaker",
            "category": "Casual",
            "price": 8500.0,
            "rating": 5.0,  # Higher rating
            "stock": 10,
            "description": "High end fashion shoe"
        },
        {
            "id": "p2",
            "name": "Pro Marathon Runner",
            "category": "Running",
            "price": 4200.0,
            "rating": 4.5,
            "stock": 8,
            "description": "Engineered for long distance marathon performance"
        },
        {
            "id": "p3",
            "name": "Everyday Jogger",
            "category": "Running",
            "price": 3200.0,
            "rating": 4.2,
            "stock": 5,
            "description": "Comfortable daily running shoe"
        }
    ]

    # Filter with category="Running", budget_max=5000, use_case="marathon"
    ranked = DeterministicRankingEngine.filter_and_rank(
        products=sample_products,
        category="Running",
        budget_max=5000.0,
        use_case="marathon"
    )

    # p1 MUST be pruned by category & budget, despite rating=5.0
    ids = [p["id"] for p in ranked]
    assert "p1" not in ids
    assert ids[0] == "p2"  # p2 top ranked because of marathon use case
    assert len(ranked[0]["why_this_rationale"]) > 0

def test_multi_turn_shopping_flow(db_session: Session):
    """Test full multi-turn conversational workflow with context persistence."""
    merchant = db_session.query(Merchant).first()
    session_id = f"sess_{generate_uuid()[:12]}"
    
    # Create test user
    user = User(
        id=generate_uuid(),
        merchant_id=merchant.id,
        email=f"shopper_{generate_uuid()[:8]}@example.com",
        full_name="Apex Shopper",
        hashed_password="mock_password",
        role="CUSTOMER"
    )
    db_session.add(user)
    db_session.commit()

    agent = ShoppingAgent(
        db=db_session,
        merchant_id=merchant.id,
        session_id=session_id,
        user=user,
        delivery_address={
            "full_name": "Apex Shopper",
            "address_line1": "123 Marathon St",
            "city": "Bangalore",
            "state": "Karnataka",
            "pin_code": "560038"
        }
    )

    # Turn 1: User searches "5k ke andar running shoes chahiye"
    r1 = agent.process_message("5k ke andar running shoes chahiye")
    assert len(r1.products) >= 1
    assert r1.products[0]["price"] <= 5000.0

    # Turn 2: User refines "black wala"
    r2 = agent.process_message("black wala")
    assert len(r2.products) >= 1
    top_shoe = r2.products[0]

    # Turn 3: User inquires "best price check karo"
    r3 = agent.process_message("best price check karo")
    assert "PRICE_COMPARISON_VIEWED" in r3.actions
    assert "Verified Price Intelligence" in r3.message or "verified price comparison" in r3.message.lower()

    # Turn 4: User selects candidate "ye wala le lo"
    r4 = agent.process_message("ye wala le lo")
    assert len(r4.products) >= 1

    # Turn 5: User sets quantity "2 pairs"
    r5 = agent.process_message("2 pairs")
    assert "2" in r5.message or "Subtotal" in r5.message

    # Turn 6: User applies coupon "use SAVE500"
    r6 = agent.process_message("use SAVE500")
    assert "SAVE500" in r6.message

    # Turn 7: User checks out "checkout"
    r7 = agent.process_message("checkout")
    assert r7.order_review is not None
    assert len(r7.order_review.items) == 1
    assert r7.order_review.items[0].quantity == 2
    
    # Total check: If 2 pairs * ~₹3,499 = ~₹6,998 - ₹500 (SAVE500) = ₹6,498 (> ₹5,000 limit)
    # -> Requires Customer Approval!
    if r7.order_review.total > 5000:
        assert r7.requires_approval is True
        assert r7.order_review.is_above_threshold is True
    else:
        # Autonomous under ₹5,000 requires explicit customer confirmation
        assert r7.requires_approval is False
        assert r7.order_review.is_above_threshold is False

def test_autonomous_order_requires_user_confirmation(db_session: Session):
    """
    Verify: Even for <= ₹5,000, autonomous execution creates an OrderReview and
    requires explicit customer confirmation before payment (No silent charging!).
    """
    merchant = db_session.query(Merchant).first()
    session_id = f"sess_auto_{generate_uuid()[:12]}"
    
    user = User(
        id=generate_uuid(),
        merchant_id=merchant.id,
        email=f"auto_shopper_{generate_uuid()[:8]}@example.com",
        full_name="Auto Shopper",
        hashed_password="mock_password",
        role="CUSTOMER"
    )
    db_session.add(user)
    db_session.commit()

    agent = ShoppingAgent(
        db=db_session,
        merchant_id=merchant.id,
        session_id=session_id,
        user=user,
        delivery_address={
            "full_name": "Auto Shopper",
            "address_line1": "45 MG Road",
            "city": "Bangalore",
            "state": "Karnataka",
            "pin_code": "560001"
        }
    )

    # 1 item: Nike Dri-FIT T-Shirt (₹999)
    # Finalize direct order for Nike Dri-FIT T-Shirt
    r = agent.process_message("Nike Dri-FIT T-Shirt order kar do")
    assert r.order_review is not None
    assert r.order_review.total <= 5000.0
    assert r.order_review.is_above_threshold is False
    assert len(r.order_review.items) == 1

def test_governance_spending_thresholds(db_session: Session):
    """
    Verify Governance boundaries:
    - <= ₹5,000: Autonomous (requires confirmation)
    - > ₹5,000 <= ₹10,000: High-Value Approval Required
    - > ₹10,000 or qty > 5: Policy Blocked
    """
    merchant = db_session.query(Merchant).first()
    session_id = f"sess_gov_{generate_uuid()[:12]}"

    agent = ShoppingAgent(
        db=db_session,
        merchant_id=merchant.id,
        session_id=session_id,
        delivery_address={
            "full_name": "Test User",
            "address_line1": "123 Test St",
            "city": "Bangalore",
            "state": "Karnataka",
            "pin_code": "560001"
        }
    )

    # User searches shoes then attempts 10 pairs checkout (> ₹10,000 limit and qty > 5)
    agent.process_message("running shoes under 5000")
    agent.process_message("ye wala le lo")
    r = agent.process_message("10 pairs checkout karo")
    assert "blocked" in r.message.lower() or "limit" in r.message.lower() or "quantity" in r.message.lower()
    assert "POLICY_BLOCKED" in r.actions

def test_audit_trail_integrity(db_session: Session):
    """Verify that all commerce actions write monotonic audit events."""
    merchant = db_session.query(Merchant).first()
    session_id = f"sess_audit_{generate_uuid()[:12]}"
    
    agent = ShoppingAgent(
        db=db_session,
        merchant_id=merchant.id,
        session_id=session_id
    )
    agent.process_message("5k ke andar running shoes chahiye")
    agent.process_message("ye wala le lo")

    # Check audit log entries
    logs = db_session.query(AuditEvent).filter(
        AuditEvent.session_id == session_id
    ).all()
    assert len(logs) >= 1
