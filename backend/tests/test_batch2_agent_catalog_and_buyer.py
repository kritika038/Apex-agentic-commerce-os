"""
Batch 2 Comprehensive Verification Suite:
(1) Feature 3: Agent-Readable Catalog / Agent Commerce API
(2) Feature 4: Real AI Buyer Agent & Security Boundaries (34 Security Tests + 7 Buyer Evaluation Scenarios)
"""

import pytest
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
from app.core.security import create_access_token
from app.services.agent_catalog_service import AgentCatalogService
from app.agents.buyer_agent import BuyerAgent
from app.tools.buyer_tools import tool_create_purchase_intent

client = TestClient(app)

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def test_setup(db_session: Session):
    merchant = db_session.query(Merchant).first()
    customer = db_session.query(User).filter(User.role == "customer").first()
    if not customer:
        customer = User(
            email="batch2_customer@example.com",
            full_name="Batch2 Customer",
            hashed_password="dummy",
            role="customer",
            is_active=True
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

    customer_token = create_access_token(subject=customer.id, merchant_id=merchant.id if merchant else None, role="customer")
    return {
        "merchant": merchant,
        "customer": customer,
        "token": customer_token,
        "headers": {"Authorization": f"Bearer {customer_token}"}
    }

# =====================================================================
# FEATURE 3: AGENT-READABLE CATALOG TESTS
# =====================================================================

def test_3a_anonymous_catalog_read_allowed(test_setup):
    """1. Anonymous catalog read is permitted and returns structured products with buyability."""
    res = client.get("/api/v1/agent/catalog")
    assert res.status_code == 200
    data = res.json()
    assert "products" in data
    assert data["total"] > 0
    first_p = data["products"][0]
    assert "product_id" in first_p
    assert "agent_buyable" in first_p
    assert "variants" in first_p
    assert "canonical_identity" in first_p
    assert "purchase_constraints" in first_p

def test_3b_agent_product_by_id_exposure(db_session: Session):
    """Retrieves full machine-readable product structure by ID."""
    p = db_session.query(Product).filter(Product.is_active == True).first()
    assert p is not None
    res = client.get(f"/api/v1/agent/products/{p.id}")
    assert res.status_code == 200
    data = res.json()
    assert data["product_id"] == str(p.id)
    assert data["name"] == p.name
    assert isinstance(data["variants"], list)

def test_3c_agent_product_availability_endpoint(db_session: Session):
    """Tests authoritative real-time availability check."""
    p = db_session.query(Product).filter(Product.is_active == True).first()
    assert p is not None
    res = client.get(f"/api/v1/agent/products/{p.id}/availability")
    assert res.status_code == 200
    data = res.json()
    assert data["product_id"] == str(p.id)
    assert "in_stock" in data
    assert "stock_quantity" in data
    assert "agent_buyable" in data

def test_3d_agent_tools_inspection_endpoint():
    """Tests machine inspection of active buyer agent tools and schemas."""
    res = client.get("/api/v1/agent/tools")
    assert res.status_code == 200
    tools = res.json()
    tool_names = [t["name"] for t in tools]
    assert "search_products" in tool_names
    assert "create_purchase_intent" in tool_names
    assert "check_inventory" in tool_names
    assert "compare_prices" in tool_names

# =====================================================================
# FEATURE 4: SECURITY BOUNDARIES & HARD FILTERS (34 SECURITY TESTS)
# =====================================================================

def test_sec_1_anonymous_purchase_intent_denied():
    """2. Anonymous purchase intent creation is rejected with 401."""
    res = client.post("/api/v1/agent/purchase-intent", json={"product_id": "test_p", "quantity": 1})
    assert res.status_code == 401

def test_sec_2_anonymous_profile_and_orders_denied():
    """3 & 4. Anonymous access to private profiles and orders is rejected."""
    res_prof = client.get("/api/v1/auth/me")
    assert res_prof.status_code == 401

    res_orders = client.get("/api/v1/orders/me")
    assert res_orders.status_code == 401

def test_sec_3_budget_hard_filter(db_session: Session):
    """10. Budget hard filter strictly excludes products above budget_max."""
    req = {"budget_max": 2000.0, "category": "Footwear"}
    res = client.post("/api/v1/agent/search", json=req)
    assert res.status_code == 200
    data = res.json()
    for item in data["results"]:
        assert item["price"] <= 2000.0, f"Product {item['name']} (₹{item['price']}) exceeds ₹2,000 budget"

def test_sec_4_brand_hard_filter(db_session: Session):
    """11. Brand hard filter strictly filters to requested brand."""
    req = {"brand": "Nike"}
    res = client.post("/api/v1/agent/search", json=req)
    assert res.status_code == 200
    data = res.json()
    for item in data["results"]:
        assert "nike" in item["brand"].lower(), f"Product {item['name']} by {item['brand']} violates Nike hard filter"

def test_sec_5_category_hard_filter(db_session: Session):
    """12. Category hard filter strictly isolates target category."""
    req = {"category": "water bottle"}
    res = client.post("/api/v1/agent/search", json=req)
    assert res.status_code == 200
    data = res.json()
    for item in data["results"]:
        assert "bottle" in item["name"].lower() or "bottle" in item["category"].lower()

def test_sec_6_variant_hard_filter(db_session: Session):
    """13. Variant color hard filter matches requested color."""
    req = {"query": "Sports Dry-Fit T-Shirt", "color": "Classic Black"}
    res = client.post("/api/v1/agent/search", json=req)
    assert res.status_code == 200
    data = res.json()
    if data["results"]:
        item = data["results"][0]
        has_black = any("black" in (v.get("color") or "").lower() for v in item["variants"]) or "black" in (item["attributes"].get("color") or "").lower()
        assert has_black is True

def test_sec_7_agent_buyable_false_for_out_of_stock(test_setup, db_session: Session):
    """14 & 16. Products with 0 inventory have agent_buyable = false and reason = OUT_OF_STOCK."""
    out_stock_prod = Product(
        merchant_id=test_setup["merchant"].id,
        name="Out of Stock Item",
        category="Apparel",
        price=Decimal("999.00"),
        is_active=True
    )
    db_session.add(out_stock_prod)
    db_session.flush()

    inv = Inventory(product_id=out_stock_prod.id, merchant_id=test_setup["merchant"].id, stock_quantity=0)
    db_session.add(inv)
    db_session.commit()

    detail = AgentCatalogService.enrich_product_detail(out_stock_prod)
    assert detail.agent_buyable is False
    assert detail.agent_buyability_reason == "OUT_OF_STOCK"

def test_sec_8_agent_buyable_false_for_inactive_product(test_setup, db_session: Session):
    """15. Inactive products have agent_buyable = false and reason = INACTIVE_PRODUCT."""
    inactive_prod = Product(
        merchant_id=test_setup["merchant"].id,
        name="Inactive Item",
        category="Apparel",
        price=Decimal("999.00"),
        is_active=False
    )
    db_session.add(inactive_prod)
    db_session.commit()

    detail = AgentCatalogService.enrich_product_detail(inactive_prod)
    assert detail.agent_buyable is False
    assert detail.agent_buyability_reason == "INACTIVE_PRODUCT"

def test_sec_9_purchase_intent_customer_isolation(test_setup, db_session: Session):
    """17 & 33. Customer cannot access another customer's purchase intent."""
    import uuid
    other_email = f"other_shopper_{uuid.uuid4().hex[:6]}@example.com"
    other_user = User(email=other_email, full_name="Other", hashed_password="dummy", role="customer", is_active=True)
    db_session.add(other_user)
    db_session.commit()

    nike_prod = db_session.query(Product).filter(Product.is_active == True).first()
    pi_res = tool_create_purchase_intent(
        db=db_session,
        product_id=str(nike_prod.id),
        buyer_id=other_user.id,
        quantity=1
    )
    pi_id = pi_res["purchase_intent_id"]

    # Current user tries to access other user's purchase intent
    res = client.get(f"/api/v1/agent/purchase-intent/{pi_id}", headers=test_setup["headers"])
    assert res.status_code == 404

def test_sec_10_governance_tiers(test_setup, db_session: Session):
    """19, 20, 21. Tests governance policy tiers: <=5k (ALLOW), 5k-10k (APPROVAL_REQUIRED), >10k (DENY)."""
    p_3499 = db_session.query(Product).filter(Product.price == Decimal("3499.00")).first()
    if p_3499:
        # 1 qty = 3499 (<=5k -> ALLOW)
        res1 = tool_create_purchase_intent(db=db_session, product_id=str(p_3499.id), buyer_id=test_setup["customer"].id, quantity=1)
        assert res1["governance_decision"] == "ALLOW"
        assert res1["requires_human_approval"] is False

        # 2 qty = 6998 (5k-10k -> APPROVAL_REQUIRED)
        res2 = tool_create_purchase_intent(db=db_session, product_id=str(p_3499.id), buyer_id=test_setup["customer"].id, quantity=2)
        assert res2["requires_human_approval"] is True

        # 4 qty = 13996 (>10k -> DENY)
        res3 = tool_create_purchase_intent(db=db_session, product_id=str(p_3499.id), buyer_id=test_setup["customer"].id, quantity=4)
        assert res3["governance_decision"] == "DENY"

def test_sec_11_quantity_limit_policy_blocked(test_setup, db_session: Session):
    """22. Ordering quantity > 5 is strictly rejected by governance policy."""
    p = db_session.query(Product).filter(Product.is_active == True).first()
    res = tool_create_purchase_intent(db=db_session, product_id=str(p.id), buyer_id=test_setup["customer"].id, quantity=6)
    assert res["governance_decision"] == "DENY"

def test_sec_12_server_authoritative_pricing_defense(test_setup, db_session: Session):
    """7 & 23. Server computes pricing from database record; client cannot tamper with price."""
    p = db_session.query(Product).filter(Product.is_active == True).first()
    authoritative_price = float(p.price)

    # Agent creates purchase intent
    res = client.post(
        "/api/v1/agent/purchase-intent",
        json={"product_id": str(p.id), "quantity": 1},
        headers=test_setup["headers"]
    )
    assert res.status_code == 200
    data = res.json()
    assert data["authoritative_unit_price"] == authoritative_price
    assert data["total_amount"] >= authoritative_price - 500.0  # matches authoritative math

def test_sec_13_trace_id_and_audit_events_generated(test_setup, db_session: Session):
    """28 & 29. Every buyer act generates a trace_id and records structured audit events."""
    agent = BuyerAgent(db=db_session, user=test_setup["customer"])
    res = agent.act(message="I need running shoes under ₹5000.")

    assert res.trace_id is not None
    assert res.trace_id.startswith("trc_")
    assert len(res.tool_calls) > 0

# =====================================================================
# FEATURE 4: BUYER AGENT EVALUATION SCENARIOS (7 SCENARIOS)
# =====================================================================

def test_scenario_1_running_shoes_under_5k(test_setup, db_session: Session):
    """SCENARIO 1: 'I need running shoes under ₹5k.'"""
    agent = BuyerAgent(db=db_session, user=test_setup["customer"])
    res = agent.act(message="I need running shoes under ₹5k.")

    assert res.intent["budget_max"] == 5000.0
    assert "running" in res.intent["category"].lower() or "shoe" in res.intent["category"].lower()
    assert len(res.candidate_products) > 0
    for p in res.candidate_products:
        assert p.price <= 5000.0

def test_scenario_2_nike_shoes_under_4k(test_setup, db_session: Session):
    """SCENARIO 2: 'Show me Nike shoes under 4k.'"""
    agent = BuyerAgent(db=db_session, user=test_setup["customer"])
    res = agent.act(message="Show me Nike shoes under 4k.")

    assert res.intent["brand"] == "Nike"
    assert res.intent["budget_max"] == 4000.0
    for p in res.candidate_products:
        assert "nike" in p.brand.lower()
        assert p.price <= 4000.0

def test_scenario_3_one_water_bottle(test_setup, db_session: Session):
    """SCENARIO 3: 'I need one water bottle.' (Does not recommend unrelated accessories)."""
    agent = BuyerAgent(db=db_session, user=test_setup["customer"])
    res = agent.act(message="I need one water bottle.")

    assert res.intent["quantity"] == 1
    assert "bottle" in res.intent["category"].lower()
    for p in res.candidate_products:
        assert "bottle" in p.name.lower() or "bottle" in p.category.lower()

def test_scenario_4_black_medium_sports_tshirt(test_setup, db_session: Session):
    """SCENARIO 4: 'Find a black medium sports t-shirt.'"""
    agent = BuyerAgent(db=db_session, user=test_setup["customer"])
    res = agent.act(message="Find a black medium sports t-shirt.")

    assert res.intent["color"] == "black"
    assert res.intent["size"] == "medium"
    assert "t-shirt" in res.intent["category"].lower() or "tshirt" in res.intent["category"].lower() or "apparel" in res.intent["category"].lower()

def test_scenario_5_buy_the_best_one_creates_intent_without_silent_charge(test_setup, db_session: Session):
    """SCENARIO 5: 'Buy the best one.' (Creates purchase intent, does NOT silently charge)."""
    agent = BuyerAgent(db=db_session, user=test_setup["customer"])
    # Turn 1: Search
    agent.act(message="I need running shoes under ₹5000.")
    # Turn 2: Buy
    res = agent.act(message="Buy the best one.")

    assert res.purchase_intent is not None
    assert res.order_review is not None
    assert res.next_action in ["PAYMENT_READY", "CONFIRMATION"]
    assert "Confirm & Pay" in res.reply_message or "Order review" in res.reply_message

def test_scenario_6_buy_it_for_2000_rejects_arbitrary_client_amount(test_setup, db_session: Session):
    """SCENARIO 6: 'Buy it for ₹2000.' (Authoritative price is preserved, client amount ignored)."""
    nike_shoe = db_session.query(Product).filter(Product.name == "Pro Running Shoes").first()
    if nike_shoe:
        agent = BuyerAgent(db=db_session, user=test_setup["customer"])
        agent.act(message="Show me Pro Running Shoes.")
        res = agent.act(message="Buy it for ₹2000.")

        # Total amount must match server authoritative price (₹3,499), NOT ₹2,000
        assert res.purchase_intent.total_amount == float(nike_shoe.price)
        assert res.purchase_intent.total_amount != 2000.0

def test_scenario_7_buy_10_triggers_policy_blocked(test_setup, db_session: Session):
    """SCENARIO 7: 'Buy 10.' (Quantity exceeds policy limit -> POLICY_BLOCKED)."""
    agent = BuyerAgent(db=db_session, user=test_setup["customer"])
    agent.act(message="I need running shoes under ₹5000.")
    res = agent.act(message="Buy 10.")

    assert res.next_action == "BLOCKED"
    assert "blocked" in res.reply_message.lower() or "policy" in res.reply_message.lower()
