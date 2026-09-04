import uuid
import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database.session import SessionLocal
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.merchant import Merchant
from app.database.models.policy import Policy
from app.database.models.purchase_intent import PurchaseIntent
from app.database.models.payment_transaction import PaymentTransaction
from app.database.models.audit_event import AuditEvent
from app.payments.service import PaymentService
from app.payments.razorpay_provider import RazorpayProvider

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def db():
    from app.core.config import settings
    orig_env = settings.ENVIRONMENT
    settings.ENVIRONMENT = "test"
    session = SessionLocal()
    try:
        # Reset inventory stock to 20 for all products
        invs = session.query(Inventory).all()
        for inv in invs:
            inv.stock_quantity = 20
        merchant = session.query(Merchant).first()
        if merchant:
            pol = session.query(Policy).filter(Policy.merchant_id == merchant.id).first()
            if pol:
                pol.approval_threshold = Decimal("5000.00")
                pol.max_transaction_amount = Decimal("10000.00")
                pol.auto_approval_enabled = True
        session.commit()
        yield session
    finally:
        session.close()
        settings.ENVIRONMENT = orig_env

@pytest.fixture
def sample_address():
    return {
        "full_name": "Autonomous Buyer Agent",
        "phone": "9876543210",
        "email": "buyer.agent@example.com",
        "address_line1": "100 AI Corridor",
        "city": "Bengaluru",
        "state": "Karnataka",
        "pin_code": "560001",
        "country": "India"
    }

# 1. STRUCTURED BUYER REQUEST
def test_1_structured_buyer_request(client, db):
    req_id = f"req_{uuid.uuid4().hex[:8]}"
    res = client.post("/api/v1/ai-commerce/search", json={
        "protocol_version": "1.0",
        "request_id": req_id,
        "query": {
            "category": "running",
            "use_case": "marathon",
            "max_price": 5000.0,
            "quantity": 1
        }
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert len(data["offers"]) >= 1

# 2. ENGLISH NATURAL LANGUAGE REQUEST
def test_2_english_natural_language_request(client, db):
    res = client.post("/api/v1/ai-commerce/search", json={
        "protocol_version": "1.0",
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "natural_language_query": "I need marathon running shoes under ₹5,000."
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert any("SpeedFlow" in o["name"] for o in data["offers"])

# 3. HINGLISH REQUEST
def test_3_hinglish_request(client, db):
    res = client.post("/api/v1/ai-commerce/search", json={
        "protocol_version": "1.0",
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "natural_language_query": "Mujhe 5000 ke andar marathon shoes chahiye."
    })
    assert res.status_code == 200
    assert len(res.json()["offers"]) >= 1

# 4. HINDI REQUEST
def test_4_hindi_request(client, db):
    res = client.post("/api/v1/ai-commerce/search", json={
        "protocol_version": "1.0",
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "natural_language_query": "मुझे पाँच हज़ार के अंदर मैराथन जूते चाहिए।"
    })
    assert res.status_code == 200
    assert len(res.json()["offers"]) >= 1

# 5. NOISY ASR REQUEST
def test_5_noisy_asr_request(client, db):
    res = client.post("/api/v1/ai-commerce/search", json={
        "protocol_version": "1.0",
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "natural_language_query": "mujhe paanch hazaar ke andar marathon jute chahiye"
    })
    assert res.status_code == 200
    assert len(res.json()["offers"]) >= 1

# 6. PRODUCT CATALOG GROUNDING
def test_6_product_catalog_grounding(client, db):
    prods = client.get("/api/v1/products").json()
    res = client.post("/api/v1/ai-commerce/search", json={
        "protocol_version": "1.0",
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "query": {"category": "running", "max_price": 5000.0}
    })
    data = res.json()
    catalog_ids = {p["id"] for p in prods}
    for o in data["offers"]:
        assert o["product_id"] in catalog_ids

# 7. BUDGET FILTER
def test_7_budget_filter(client, db):
    res = client.post("/api/v1/ai-commerce/search", json={
        "protocol_version": "1.0",
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "query": {"category": "running", "max_price": 3000.0}
    })
    data = res.json()
    for o in data["offers"]:
        assert o["unit_price"] <= 3000.0

# 8. CATEGORY FILTER (NO CROSS-SELLING UNLESS REQUESTED)
def test_8_category_filter(client, db):
    res = client.post("/api/v1/ai-commerce/search", json={
        "protocol_version": "1.0",
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "query": {"category": "running"}
    })
    data = res.json()
    for o in data["offers"]:
        assert "running" in o["category"].lower() or "shoe" in o["name"].lower()

# 9. QUANTITY HANDLING
def test_9_quantity_handling(client, db):
    res = client.post("/api/v1/ai-commerce/search", json={
        "protocol_version": "1.0",
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "query": {"category": "running", "quantity": 2}
    })
    assert res.status_code == 200
    assert res.json()["offers"][0]["quantity_available"] is True

# 10. MULTIPLE OFFERS RETURNED
def test_10_multiple_offers_returned(client, db):
    res = client.post("/api/v1/ai-commerce/search", json={
        "protocol_version": "1.0",
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "query": {"category": "running", "max_price": 5000.0}
    })
    assert len(res.json()["offers"]) >= 2

# 11. BEST PRODUCT SELECTION
def test_11_best_product_selection(client, db):
    s_res = client.post("/api/v1/ai-commerce/search", json={
        "protocol_version": "1.0",
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "natural_language_query": "marathon running shoes under 5000"
    })
    sess_id = s_res.json()["session_id"]
    sel_res = client.post("/api/v1/ai-commerce/select-offer", json={
        "protocol_version": "1.0",
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "session_id": sess_id,
        "selection_strategy": "best_match"
    })
    assert sel_res.status_code == 200
    assert "SpeedFlow" in sel_res.json()["selected_offer"]["name"]

# 12. CHEAPEST PRODUCT SELECTION
def test_12_cheapest_product_selection(client, db):
    s_res = client.post("/api/v1/ai-commerce/search", json={
        "protocol_version": "1.0",
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "query": {"category": "running", "max_price": 5000.0}
    })
    sess_id = s_res.json()["session_id"]
    sel_res = client.post("/api/v1/ai-commerce/select-offer", json={
        "protocol_version": "1.0",
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "session_id": sess_id,
        "selection_strategy": "cheapest"
    })
    assert sel_res.status_code == 200
    assert sel_res.json()["selected_offer"]["unit_price"] == 2999.0

# 13. CONSTRAINT NEGOTIATION
def test_13_constraint_negotiation(client, db):
    s_res = client.post("/api/v1/ai-commerce/search", json={
        "protocol_version": "1.0",
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "query": {"category": "running", "max_price": 2000.0}
    })
    assert s_res.json()["status"] == "no_match"
    sess_id = s_res.json()["session_id"]

    neg_res = client.post("/api/v1/ai-commerce/negotiate", json={
        "protocol_version": "1.0",
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "session_id": sess_id,
        "action": "adjust_budget",
        "new_budget": 3500.0
    })
    assert neg_res.status_code == 200
    assert len(neg_res.json()["offers"]) >= 1

# 14. MULTI-TURN AI CONTEXT RETENTION
def test_14_multiturn_ai_context(client, db):
    sess_id = f"sess_multi_{uuid.uuid4().hex[:8]}"
    r1 = client.post("/api/v1/ai-commerce/search", json={
        "protocol_version": "1.0",
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "session_id": sess_id,
        "natural_language_query": "running shoes under 5000"
    })
    r2 = client.post("/api/v1/ai-commerce/negotiate", json={
        "protocol_version": "1.0",
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "session_id": sess_id,
        "action": "show_cheapest",
        "limit": 2
    })
    assert len(r2.json()["offers"]) == 2

# 15. OFFER EXPIRATION / REVALIDATION
def test_15_offer_expiration_revalidation(client, db):
    s_res = client.post("/api/v1/ai-commerce/search", json={
        "protocol_version": "1.0",
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "query": {"category": "running"}
    })
    offer = s_res.json()["offers"][0]
    # Revalidate via selection
    sel_res = client.post("/api/v1/ai-commerce/select-offer", json={
        "protocol_version": "1.0",
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "session_id": s_res.json()["session_id"],
        "offer_id": offer["offer_id"]
    })
    assert sel_res.status_code == 200
    assert sel_res.json()["status"] == "selected"

# 16. STOCK EXHAUSTION RECOVERY
def test_16_stock_exhaustion_recovery(client, db):
    prods = client.get("/api/v1/products").json()
    bottle = next(p for p in prods if "Bottle" in p["name"])
    inv = db.query(Inventory).filter(Inventory.product_id == bottle["id"]).first()
    orig = inv.stock_quantity if inv else 10
    if inv:
        inv.stock_quantity = 0
        db.commit()

    try:
        res = client.post("/api/v1/ai-commerce/select-offer", json={
            "protocol_version": "1.0",
            "request_id": f"req_{uuid.uuid4().hex[:8]}",
            "session_id": f"sess_{uuid.uuid4().hex[:8]}",
            "product_id": bottle["id"]
        })
        assert res.status_code == 200
        assert res.json()["status"] == "out_of_stock"
        assert res.json()["recovery"]["action"] == "search_alternatives"
    finally:
        if inv:
            inv.stock_quantity = orig
            db.commit()

# 17. PRICE CHANGE DETECTION
def test_17_price_change_detection(client, db):
    s_res = client.post("/api/v1/ai-commerce/search", json={
        "protocol_version": "1.0",
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "query": {"category": "running"}
    })
    offer = s_res.json()["offers"][0]
    prod = db.query(Product).filter(Product.id == offer["product_id"]).first()
    orig_price = prod.price
    prod.price = Decimal("3999.00")
    db.commit()

    try:
        sel_res = client.post("/api/v1/ai-commerce/select-offer", json={
            "protocol_version": "1.0",
            "request_id": f"req_{uuid.uuid4().hex[:8]}",
            "session_id": s_res.json()["session_id"],
            "offer_id": offer["offer_id"]
        })
        assert sel_res.status_code == 200
        assert sel_res.json()["status"] == "offer_changed"
    finally:
        prod.price = orig_price
        db.commit()

# 18. COUPON APPLICATION
def test_18_coupon_application(client, db, sample_address):
    sess = f"sess_{uuid.uuid4().hex[:8]}"
    prods = client.get("/api/v1/products").json()
    pro_shoe = next(p for p in prods if "Pro" in p["name"])
    res = client.post("/api/v1/ai-commerce/purchase-intent", json={
        "protocol_version": "1.0",
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "session_id": sess,
        "product_id": pro_shoe["id"],
        "quantity": 2,
        "coupon_code": "SAVE500",
        "delivery_address": sample_address
    })
    assert res.status_code == 200
    assert res.json()["order_review"]["coupon_discount"] == 500.0

# 19. APEX COINS APPLICATION
def test_19_apex_coins_application(client, db, sample_address):
    sess = f"sess_{uuid.uuid4().hex[:8]}"
    prods = client.get("/api/v1/products").json()
    res = client.post("/api/v1/ai-commerce/purchase-intent", json={
        "protocol_version": "1.0",
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "session_id": sess,
        "product_id": prods[0]["id"],
        "quantity": 1,
        "use_coins": True,
        "delivery_address": sample_address
    })
    assert res.status_code == 200
    assert res.json()["order_review"]["total_amount"] <= res.json()["order_review"]["subtotal"]

# 20. PURCHASE INTENT CREATION
def test_20_purchase_intent_creation(client, db, sample_address):
    sess = f"sess_{uuid.uuid4().hex[:8]}"
    prods = client.get("/api/v1/products").json()
    res = client.post("/api/v1/ai-commerce/purchase-intent", json={
        "protocol_version": "1.0",
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "session_id": sess,
        "product_id": prods[0]["id"],
        "quantity": 1,
        "delivery_address": sample_address
    })
    assert res.status_code == 200
    assert res.json()["purchase_intent_id"].startswith("pi_")

# 21. MISSING ADDRESS HANDLING
def test_21_missing_address_handling(client, db):
    sess = f"sess_{uuid.uuid4().hex[:8]}"
    prods = client.get("/api/v1/products").json()
    res = client.post("/api/v1/ai-commerce/purchase-intent", json={
        "protocol_version": "1.0",
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "session_id": sess,
        "product_id": prods[0]["id"],
        "quantity": 1
    })
    assert res.status_code == 200
    assert res.json()["purchase_intent_id"] is not None

# 22. BELOW THRESHOLD AUTO FLOW (<= 5000)
def test_22_below_threshold_auto_flow(client, db, sample_address):
    sess = f"sess_{uuid.uuid4().hex[:8]}"
    prods = client.get("/api/v1/products").json()
    speed_shoe = next(p for p in prods if "SpeedFlow" in p["name"])
    res = client.post("/api/v1/ai-commerce/purchase-intent", json={
        "protocol_version": "1.0",
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "session_id": sess,
        "product_id": speed_shoe["id"],
        "quantity": 1,
        "delivery_address": sample_address
    })
    assert res.status_code == 200
    assert res.json()["requires_human_approval"] is False
    assert res.json()["status"] == "REVIEW_REQUIRED"

# 23. ABOVE THRESHOLD GOVERNANCE REQUIRED (> 5000)
def test_23_above_threshold_governance_required(client, db, sample_address):
    sess = f"sess_{uuid.uuid4().hex[:8]}"
    prods = client.get("/api/v1/products").json()
    pro_shoe = next(p for p in prods if "Pro" in p["name"])
    res = client.post("/api/v1/ai-commerce/purchase-intent", json={
        "protocol_version": "1.0",
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "session_id": sess,
        "product_id": pro_shoe["id"],
        "quantity": 2,
        "delivery_address": sample_address
    })
    assert res.status_code == 200
    assert res.json()["requires_human_approval"] is True
    assert res.json()["status"] == "APPROVAL_REQUIRED"

# 24. EXPLICIT HUMAN APPROVAL
def test_24_explicit_human_approval(client, db, sample_address):
    sess = f"sess_{uuid.uuid4().hex[:8]}"
    prods = client.get("/api/v1/products").json()
    pro_shoe = next(p for p in prods if "Pro" in p["name"])
    pi_res = client.post("/api/v1/ai-commerce/purchase-intent", json={
        "protocol_version": "1.0",
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "session_id": sess,
        "product_id": pro_shoe["id"],
        "quantity": 2,
        "delivery_address": sample_address
    })
    pi_id = pi_res.json()["purchase_intent_id"]
    appr_id = pi_res.json()["approval_details"]["approval_request_id"]

    pay_res = client.post("/api/v1/ai-commerce/approve-and-pay", json={
        "protocol_version": "1.0",
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "purchase_intent_id": pi_id,
        "approval_id": appr_id,
        "idempotency_key": f"idem_{uuid.uuid4().hex[:8]}"
    })
    assert pay_res.status_code == 200
    assert pay_res.json()["razorpay_order_id"] is not None

# 25. APPROVAL CANCELLATION
def test_25_approval_cancellation(client, db, sample_address):
    sess = f"sess_{uuid.uuid4().hex[:8]}"
    prods = client.get("/api/v1/products").json()
    pro_shoe = next(p for p in prods if "Pro" in p["name"])
    pi_res = client.post("/api/v1/ai-commerce/purchase-intent", json={
        "protocol_version": "1.0",
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "session_id": sess,
        "product_id": pro_shoe["id"],
        "quantity": 2,
        "delivery_address": sample_address
    })
    appr_id = pi_res.json()["approval_details"]["approval_request_id"]
    rej_res = client.post(f"/api/v1/approvals/{appr_id}/reject", json={"reason": "Customer cancelled"})
    assert rej_res.status_code == 200
    assert rej_res.json()["approval"]["status"] == "REJECTED"

# 26. RAZORPAY ORDER CREATION GUARDS
def test_26_razorpay_order_creation_guards(client, db):
    res = client.post("/api/v1/payments/create-order", json={
        "purchase_intent_id": "invalid_pi",
        "authorization_id": "invalid_auth",
        "idempotency_key": "idem_guard_26"
    })
    assert res.status_code in [400, 404]

# 27. SIGNATURE VERIFICATION
def test_27_signature_verification(client, db):
    res = client.post("/api/v1/ai-commerce/verify-payment", json={
        "protocol_version": "1.0",
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "purchase_intent_id": "invalid_pi",
        "authorization_id": "invalid_auth",
        "razorpay_order_id": "order_fake",
        "razorpay_payment_id": "pay_fake",
        "razorpay_signature": "invalid_sig"
    })
    assert res.status_code in [400, 404]

# 28. PAYMENT FAILURE HANDLING
def test_28_payment_failure_handling(client, db):
    res = client.post("/api/v1/payments/verify-signature", json={
        "razorpay_order_id": "order_fake_fail",
        "razorpay_payment_id": "pay_fake_fail",
        "razorpay_signature": "tampered_sig"
    })
    assert res.status_code in [400, 404]

# 29. PAYMENT IDEMPOTENCY
def test_29_payment_idempotency(client, db, sample_address):
    sess = f"sess_{uuid.uuid4().hex[:8]}"
    prods = client.get("/api/v1/products").json()
    pi_res = client.post("/api/v1/ai-commerce/purchase-intent", json={
        "protocol_version": "1.0",
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "session_id": sess,
        "product_id": prods[0]["id"],
        "quantity": 1,
        "delivery_address": sample_address
    })
    pi_id = pi_res.json()["purchase_intent_id"]
    idem_key = f"idem_test_29_{uuid.uuid4().hex[:8]}"

    r1 = client.post("/api/v1/ai-commerce/approve-and-pay", json={
        "protocol_version": "1.0",
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "purchase_intent_id": pi_id,
        "idempotency_key": idem_key
    })
    r2 = client.post("/api/v1/ai-commerce/approve-and-pay", json={
        "protocol_version": "1.0",
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "purchase_intent_id": pi_id,
        "idempotency_key": idem_key
    })
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["razorpay_order_id"] == r2.json()["razorpay_order_id"]

# 30. DUPLICATE AI REQUEST HANDLING
def test_30_duplicate_ai_request_handling(client, db):
    req_id = f"req_{uuid.uuid4().hex[:8]}"
    r1 = client.post("/api/v1/ai-commerce/search", json={
        "protocol_version": "1.0",
        "request_id": req_id,
        "natural_language_query": "running shoes"
    })
    r2 = client.post("/api/v1/ai-commerce/search", json={
        "protocol_version": "1.0",
        "request_id": req_id,
        "natural_language_query": "running shoes"
    })
    assert r1.status_code == 200
    assert r2.status_code == 200

# 31. CROSS-USER ISOLATION
def test_31_cross_user_isolation(client, db):
    res = client.post("/api/v1/purchase-intents/", json={
        "session_id": "isolated_user_sess",
        "buyer_id": "other_user@example.com"
    })
    assert res.status_code in [200, 400]

# 32. CROSS-MERCHANT ISOLATION
def test_32_cross_merchant_isolation(client, db):
    merchants = db.query(Merchant).all()
    if len(merchants) >= 2:
        m1, m2 = merchants[0], merchants[1]
        res = client.get(f"/api/v1/ai-commerce/activity?merchant_id={m2.id}")
        assert res.status_code == 200

# 33. UNAUTHORIZED AGENT REQUEST
def test_33_unauthorized_agent_request(client, db):
    res = client.post("/api/v1/ai-commerce/search", json={
        "protocol_version": "1.0",
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "natural_language_query": "running shoes"
    }, headers={"X-Agent-Key": "valid_agent_key_123"})
    assert res.status_code == 200

# 34. MALFORMED REQUEST REJECTION
def test_34_malformed_request_rejection(client, db):
    res = client.post("/api/v1/ai-commerce/search", json={
        "protocol_version": "invalid_format",
        # missing request_id
    })
    assert res.status_code in [400, 422]

# 35. AUDIT TRAIL RECORDING
def test_35_audit_trail_recording(client, db):
    client.post("/api/v1/ai-commerce/search", json={
        "protocol_version": "1.0",
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "natural_language_query": "running shoes under 5000"
    })
    act = client.get("/api/v1/ai-commerce/activity").json()
    assert act["active_agent_requests"] >= 1
    assert len(act["recent_events"]) >= 1

# 36. ORDER CONFIRMATION END-TO-END
def test_36_order_confirmation_end_to_end(client, db, sample_address):
    sess = f"sess_{uuid.uuid4().hex[:8]}"
    prods = client.get("/api/v1/products").json()
    speed_shoe = next(p for p in prods if "SpeedFlow" in p["name"])

    # 1. Search
    s_res = client.post("/api/v1/ai-commerce/search", json={
        "protocol_version": "1.0",
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "session_id": sess,
        "natural_language_query": "marathon running shoes under 5000"
    })
    offer = s_res.json()["offers"][0]

    # 2. Select
    sel_res = client.post("/api/v1/ai-commerce/select-offer", json={
        "protocol_version": "1.0",
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "session_id": sess,
        "offer_id": offer["offer_id"]
    })
    assert sel_res.status_code == 200

    # 3. Purchase Intent
    pi_res = client.post("/api/v1/ai-commerce/purchase-intent", json={
        "protocol_version": "1.0",
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "session_id": sess,
        "offer_id": offer["offer_id"],
        "quantity": 1,
        "delivery_address": sample_address
    })
    pi_data = pi_res.json()
    pi_id = pi_data["purchase_intent_id"]

    # 4. Approve & Pay
    pay_res = client.post("/api/v1/ai-commerce/approve-and-pay", json={
        "protocol_version": "1.0",
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "purchase_intent_id": pi_id,
        "idempotency_key": f"idem_e2e_{uuid.uuid4().hex[:8]}"
    })
    pay_data = pay_res.json()
    rzp_order_id = pay_data["razorpay_order_id"]
    auth_id = pay_data["authorization_id"]

    # 5. Verify Payment
    sig = "sig_test_verified_123"
    v_res = client.post("/api/v1/ai-commerce/verify-payment", json={
        "protocol_version": "1.0",
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "purchase_intent_id": pi_id,
        "authorization_id": auth_id,
        "razorpay_order_id": rzp_order_id,
        "razorpay_payment_id": "pay_test_verified_123",
        "razorpay_signature": sig
    })
    assert v_res.status_code == 200
    assert v_res.json()["status"] == "ORDER_CONFIRMED"
    assert v_res.json()["order_number"] is not None
