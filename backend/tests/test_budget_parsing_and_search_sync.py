import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.agents.intent_engine import ConversationIntentEngine
from app.agents.shopping_agent import ShoppingAgent
from app.services.discovery_service import MultimodalDiscoveryService
from app.database.models.merchant import Merchant
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.user import User
from app.auth import router as auth_router_module

@pytest.fixture
def test_catalog_setup(db: Session):
    m = Merchant(name="Apex Sports Store", domain="apex-sports.test", is_active=True)
    db.add(m)
    db.commit()
    db.refresh(m)

    # 3 Verified Running Shoes
    p1 = Product(merchant_id=m.id, name="SpeedFlow Marathon Shoes", price=Decimal("2999.00"), category="Footwear", is_active=True)
    p2 = Product(merchant_id=m.id, name="Pro Running Shoes", price=Decimal("3499.00"), category="Footwear", is_active=True)
    p3 = Product(merchant_id=m.id, name="Air Cushion Trail Running Shoes", price=Decimal("4299.00"), category="Footwear", is_active=True)
    
    # Other items
    p4 = Product(merchant_id=m.id, name="Gym Duffle Bag", price=Decimal("1899.00"), category="Bags", is_active=True)
    p5 = Product(merchant_id=m.id, name="Insulated Stainless Steel Water Bottle", price=Decimal("799.00"), category="Accessories", is_active=True)

    db.add_all([p1, p2, p3, p4, p5])
    db.commit()

    for p in [p1, p2, p3, p4, p5]:
        db.add(Inventory(merchant_id=m.id, product_id=p.id, stock_quantity=10))
    db.commit()

    return {"merchant": m, "p1": p1, "p2": p2, "p3": p3, "p4": p4, "p5": p5}

# ==========================================
# 1. BUDGET EXTRACTION & NORMALIZATION TESTS
# ==========================================

def test_1_budget_normalization_variations():
    cases = [
        ("running shoes under 500", 500.0),
        ("running shoes under ₹500", 500.0),
        ("500 ke andar jute", 500.0),
        ("500 ke aas-paas joote", 500.0),
        ("running shoes under 5k", 5000.0),
        ("running shoes under 5 k", 5000.0),
        ("5k ke andar running shoes", 5000.0),
        ("5000 ke andar jute", 5000.0),
        ("running shoes under ₹5000", 5000.0),
        ("running shoes under five thousand", 5000.0),
        ("पाँच हजार के अंदर रनिंग जूते", 5000.0),
        ("5 hazaar ke andar running shoes", 5000.0),
        ("paanch hazaar ke andar running shoes", 5000.0),
        ("₹5,000 tak ke running shoes", 5000.0),
    ]

    for query, expected_budget in cases:
        norm_text, _ = ConversationIntentEngine.normalize_text(query)
        budget, b_type, all_b = ConversationIntentEngine._extract_budget(norm_text)
        assert budget == expected_budget, f"Failed for query '{query}': got budget {budget}, expected {expected_budget}"
        assert b_type != "conflict"
        assert len(all_b) == 1

def test_2_never_convert_500_to_5000():
    norm_text, _ = ConversationIntentEngine.normalize_text("500 ke andar running shoes")
    budget, _, _ = ConversationIntentEngine._extract_budget(norm_text)
    assert budget == 500.0
    assert budget != 5000.0

# ==========================================
# 2. CONFLICTING BUDGET CONSTRAINTS
# ==========================================

def test_3_conflicting_budgets_trigger_clarification(db, test_catalog_setup):
    m = test_catalog_setup["merchant"]
    agent = ShoppingAgent(db=db, merchant_id=m.id, session_id="sess_conflict_1")

    # User mentions both 500 and 5000 in same query
    query = "500 के अंदर जूते 5000 के अंदर"
    res = agent.process_message(query)

    assert "500" in res.message
    assert "5,000" in res.message or "5000" in res.message
    assert "keep" in res.message.lower() or "budget" in res.message.lower() or "rakhu" in res.message.lower()
    assert res.products == []
    assert res.structured_intent is not None
    assert res.structured_intent.get("clarification_needed") is True
    assert res.structured_intent.get("clarification_reason") == "budget_conflict"

def test_4_conflicting_budgets_hinglish(db, test_catalog_setup):
    m = test_catalog_setup["merchant"]
    agent = ShoppingAgent(db=db, merchant_id=m.id, session_id="sess_conflict_2")

    query = "500 ke andar shoes 5000 ke andar"
    res = agent.process_message(query)

    assert "500" in res.message
    assert "5,000" in res.message or "5000" in res.message
    assert res.products == []
    assert res.structured_intent.get("clarification_needed") is True

# ==========================================
# 3. CATALOG GROUNDING & SEARCH SYNC
# ==========================================

def test_5_running_shoes_under_5k_returns_all_three(db, test_catalog_setup):
    m = test_catalog_setup["merchant"]
    agent = ShoppingAgent(db=db, merchant_id=m.id, session_id="sess_5k_sync")

    res = agent.process_message("running shoes under 5k")
    assert len(res.products) == 3
    product_names = [p["name"] for p in res.products]
    assert "SpeedFlow Marathon Shoes" in product_names
    assert "Pro Running Shoes" in product_names
    assert "Air Cushion Trail Running Shoes" in product_names
    assert res.structured_intent is not None
    assert res.structured_intent.get("max_price") == 5000.0
    assert res.structured_intent.get("category") == "Running"

def test_6_running_shoes_under_500_truthful_empty_result(db, test_catalog_setup):
    m = test_catalog_setup["merchant"]
    agent = ShoppingAgent(db=db, merchant_id=m.id, session_id="sess_500_sync")

    res = agent.process_message("running shoes under 500")
    assert len(res.products) == 0
    assert "500" in res.message
    assert "2,999" in res.message or "SpeedFlow" in res.message
    assert res.structured_intent is not None
    assert res.structured_intent.get("max_price") == 500.0

# ==========================================
# 4. MULTI-TURN CONTEXT PRESERVATION
# ==========================================

def test_7_multi_turn_shopping_context(db, test_catalog_setup):
    m = test_catalog_setup["merchant"]
    agent = ShoppingAgent(db=db, merchant_id=m.id, session_id="sess_multiturn_1")

    # Turn 1: Discover category
    r1 = agent.process_message("running shoes")
    assert len(r1.products) >= 3

    # Turn 2: Filter budget
    r2 = agent.process_message("under 5k")
    assert len(r2.products) == 3
    assert r2.structured_intent["category"] == "Running"
    assert r2.structured_intent["max_price"] == 5000.0

    # Turn 3: Ask which is best
    r3 = agent.process_message("which one is best?")
    assert len(r3.products) == 1
    assert r3.products[0]["name"] == "SpeedFlow Marathon Shoes"

    # Turn 4: Finalize selected candidate
    r4 = agent.process_message("finalize this one and order it")
    assert r4.order_review is not None
    assert len(r4.order_review.items) == 1
    assert r4.order_review.items[0].name == "SpeedFlow Marathon Shoes"
    assert r4.order_review.total == 2999.0

# ==========================================
# 5. GOOGLE OAUTH SECURITY-CRITICAL AUDIT
# ==========================================

class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload

class _FakeAsyncClient:
    def __init__(self, userinfo_payload: dict):
        self.userinfo_payload = userinfo_payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, data=None):
        return _FakeResponse(200, {"access_token": "google_test_token"})

    async def get(self, url, headers=None):
        return _FakeResponse(200, self.userinfo_payload)

def test_8_case_a_b_normal_google_account_cannot_get_merchant_role(monkeypatch, client, test_catalog_setup):
    auth_router_module.settings.GOOGLE_CLIENT_ID = "test_client_id"
    auth_router_module.settings.GOOGLE_CLIENT_SECRET = "test_client_secret"
    auth_router_module.settings.MERCHANT_ADMIN_EMAILS = "official_admin@apex.test"

    monkeypatch.setattr(
        auth_router_module.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _FakeAsyncClient({
            "sub": "google_normal_user_1",
            "email": "normal_shopper@gmail.com",
            "name": "Normal Shopper",
            "email_verified": True
        })
    )

    # Case A: Selecting Customer tab -> receives customer
    res_a = client.post("/api/v1/auth/google/callback", json={"code": "auth_code_1", "role": "customer"})
    assert res_a.status_code == 200
    assert res_a.json()["role"] == "customer"
    assert res_a.json()["user"]["role"] == "customer"

    # Case B: Selecting Merchant tab with normal account -> MUST NOT receive merchant_admin (strictly receives customer)
    res_b = client.post("/api/v1/auth/google/callback", json={"code": "auth_code_2", "role": "merchant_admin"})
    assert res_b.status_code == 200
    assert res_b.json()["role"] == "customer"
    assert res_b.json()["user"]["role"] == "customer"

def test_9_case_c_authorized_google_merchant_receives_merchant_admin(monkeypatch, client, test_catalog_setup):
    auth_router_module.settings.GOOGLE_CLIENT_ID = "test_client_id"
    auth_router_module.settings.GOOGLE_CLIENT_SECRET = "test_client_secret"
    auth_router_module.settings.MERCHANT_ADMIN_EMAILS = "official_admin@apex.test"

    monkeypatch.setattr(
        auth_router_module.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _FakeAsyncClient({
            "sub": "google_admin_user_1",
            "email": "official_admin@apex.test",
            "name": "Official Admin",
            "email_verified": True
        })
    )

    # Case C: Authorized merchant email -> receives merchant_admin
    res = client.post("/api/v1/auth/google/callback", json={"code": "auth_code_3"})
    assert res.status_code == 200
    assert res.json()["role"] == "merchant_admin"
    assert res.json()["user"]["role"] == "merchant_admin"

def test_10_case_f_g_customer_token_cannot_access_merchant_apis(monkeypatch, client, test_catalog_setup):
    auth_router_module.settings.GOOGLE_CLIENT_ID = "test_client_id"
    auth_router_module.settings.GOOGLE_CLIENT_SECRET = "test_client_secret"
    auth_router_module.settings.MERCHANT_ADMIN_EMAILS = "official_admin@apex.test"

    monkeypatch.setattr(
        auth_router_module.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _FakeAsyncClient({
            "sub": "google_cust_test_99",
            "email": "customer99@gmail.com",
            "name": "Customer 99",
            "email_verified": True
        })
    )

    login_res = client.post("/api/v1/auth/google/callback", json={"code": "code_99"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Verify /auth/me returns customer
    me_res = client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["role"] == "customer"

    # Accessing merchant APIs -> 403 Forbidden
    appr_res = client.get("/api/v1/approvals", headers=headers)
    assert appr_res.status_code == 403

    pol_res = client.get("/api/v1/policies", headers=headers)
    assert pol_res.status_code == 403

    audit_res = client.get("/api/v1/audit/events", headers=headers)
    assert audit_res.status_code == 403
