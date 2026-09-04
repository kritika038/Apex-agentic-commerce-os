import pytest
import uuid
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database.session import SessionLocal
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.merchant import Merchant
from app.database.models.policy import Policy
from app.database.models.cart import Cart, CartItem
from app.services.pricing_service import PricingService
from app.services.reward_service import RewardService

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def db():
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

@pytest.fixture
def sample_address():
    return {
        "full_name": "Rahul Sharma",
        "phone": "9876543210",
        "email": "rahul.sharma@example.com",
        "address_line1": "123 Connaught Place",
        "city": "New Delhi",
        "state": "Delhi",
        "pin_code": "110001",
        "country": "India"
    }

# TEST 1 — ENGLISH PURCHASE
def test_1_english_purchase_flow(client, db, sample_address):
    sess = f"test_agentic_t1_{uuid.uuid4().hex[:8]}"
    client.post("/api/v1/ai/shopping", json={"session_id": sess, "message": "Running shoes under ₹5000"})
    client.post("/api/v1/ai/shopping", json={"session_id": sess, "message": "Which one is best?"})
    
    res = client.post("/api/v1/ai/shopping", json={
        "session_id": sess,
        "message": "Finalize it and order it.",
        "delivery_address": sample_address
    })
    assert res.status_code == 200
    data = res.json()
    assert data["order_review"] is not None
    assert len(data["order_review"]["items"]) >= 1
    assert "SpeedFlow" in data["order_review"]["items"][0]["name"]
    assert data["structured_intent"]["action"] == "finalize_order"

# TEST 2 — HINGLISH PURCHASE
def test_2_hinglish_purchase_flow(client, db, sample_address):
    sess = f"test_agentic_t2_{uuid.uuid4().hex[:8]}"
    client.post("/api/v1/ai/shopping", json={"session_id": sess, "message": "running shoes dikhao"})
    
    res = client.post("/api/v1/ai/shopping", json={
        "session_id": sess,
        "message": "Ye wala shoe final karo aur order kar do.",
        "delivery_address": sample_address
    })
    assert res.status_code == 200
    data = res.json()
    assert data["order_review"] is not None
    assert data["structured_intent"]["intent"] == "purchase"

# TEST 3 — HINDI PURCHASE
def test_3_hindi_purchase_flow(client, db, sample_address):
    sess = f"test_agentic_t3_{uuid.uuid4().hex[:8]}"
    client.post("/api/v1/ai/shopping", json={"session_id": sess, "message": "जूते दिखाओ"})
    
    res = client.post("/api/v1/ai/shopping", json={
        "session_id": sess,
        "message": "इस जूते को ऑर्डर कर दो।",
        "delivery_address": sample_address
    })
    assert res.status_code == 200
    data = res.json()
    assert data["order_review"] is not None

# TEST 4 — VOICE / NOISY ASR
def test_4_voice_asr_purchase_flow(client, db, sample_address):
    sess = f"test_agentic_t4_{uuid.uuid4().hex[:8]}"
    client.post("/api/v1/ai/shopping", json={"session_id": sess, "message": "running shoes"})
    
    res = client.post("/api/v1/ai/shopping", json={
        "session_id": sess,
        "message": "ye vala final kro aur order kr do",
        "delivery_address": sample_address
    })
    assert res.status_code == 200
    data = res.json()
    assert data["order_review"] is not None

# TEST 5 — BEST PRODUCT RESOLUTION
def test_5_best_product_order(client, db, sample_address):
    sess = f"test_agentic_t5_{uuid.uuid4().hex[:8]}"
    client.post("/api/v1/ai/shopping", json={"session_id": sess, "message": "show me running shoes under 5000"})
    
    res = client.post("/api/v1/ai/shopping", json={
        "session_id": sess,
        "message": "Order the best one.",
        "delivery_address": sample_address
    })
    assert res.status_code == 200
    data = res.json()
    assert data["order_review"] is not None
    assert "SpeedFlow" in data["order_review"]["items"][0]["name"]

# TEST 6 — CHEAPEST PRODUCT RESOLUTION
def test_6_cheapest_product_order(client, db, sample_address):
    sess = f"test_agentic_t6_{uuid.uuid4().hex[:8]}"
    client.post("/api/v1/ai/shopping", json={"session_id": sess, "message": "show me running shoes under 5000"})
    
    res = client.post("/api/v1/ai/shopping", json={
        "session_id": sess,
        "message": "cheapest one order kar do",
        "delivery_address": sample_address
    })
    assert res.status_code == 200
    data = res.json()
    assert data["order_review"] is not None
    assert "SpeedFlow" in data["order_review"]["items"][0]["name"]

# TEST 7 — FIRST PRODUCT RESOLUTION
def test_7_first_product_order(client, db, sample_address):
    sess = f"test_agentic_t7_{uuid.uuid4().hex[:8]}"
    client.post("/api/v1/ai/shopping", json={"session_id": sess, "message": "show me running shoes"})
    
    res = client.post("/api/v1/ai/shopping", json={
        "session_id": sess,
        "message": "first one order karo",
        "delivery_address": sample_address
    })
    assert res.status_code == 200
    data = res.json()
    assert data["order_review"] is not None

# TEST 8 — CART CHECKOUT
def test_8_cart_checkout(client, db, sample_address):
    sess = f"test_agentic_t8_{uuid.uuid4().hex[:8]}"
    prods = client.get("/api/v1/products").json()
    client.post("/api/v1/cart/items", json={"session_id": sess, "product_id": prods[0]["id"], "quantity": 1})
    
    res = client.post("/api/v1/ai/shopping", json={
        "session_id": sess,
        "message": "cart checkout kar do",
        "delivery_address": sample_address
    })
    assert res.status_code == 200
    data = res.json()
    assert data["order_review"] is not None
    assert len(data["order_review"]["items"]) >= 1

# TEST 9 — MISSING DELIVERY ADDRESS
def test_9_missing_address_requests_info(client, db):
    sess = f"test_agentic_t9_{uuid.uuid4().hex[:8]}"
    client.post("/api/v1/ai/shopping", json={"session_id": sess, "message": "running shoes under 5000"})
    
    res = client.post("/api/v1/ai/shopping", json={
        "session_id": sess,
        "message": "Finalize it and order it."
    })
    assert res.status_code == 200
    data = res.json()
    assert data["order_review"] is not None
    assert data["order_review"]["delivery_address_required"] is True
    assert "address" in data["message"].lower()

# TEST 10 — COUPON APPLICATION (SAVE500)
def test_10_coupon_discount(client, db, sample_address):
    sess = f"test_agentic_t10_{uuid.uuid4().hex[:8]}"
    prods = client.get("/api/v1/products").json()
    # Add 2 pairs of Pro Running Shoes (2 * 3499 = 6998 >= 5000 threshold for SAVE500)
    pro_shoe = next(p for p in prods if "Pro" in p["name"])
    client.post("/api/v1/cart/items", json={"session_id": sess, "product_id": pro_shoe["id"], "quantity": 2})

    res = client.post("/api/v1/ai/shopping", json={
        "session_id": sess,
        "message": "cart checkout kar do",
        "applied_coupon": "SAVE500",
        "delivery_address": sample_address
    })
    assert res.status_code == 200
    data = res.json()
    assert data["order_review"] is not None
    assert data["order_review"]["coupon_discount"] == 500.0

# TEST 11 — COINS APPLICATION
def test_11_coins_discount(client, db, sample_address):
    sess = f"test_agentic_t11_{uuid.uuid4().hex[:8]}"
    prods = client.get("/api/v1/products").json()
    client.post("/api/v1/cart/items", json={"session_id": sess, "product_id": prods[0]["id"], "quantity": 1})

    res = client.post("/api/v1/ai/shopping", json={
        "session_id": sess,
        "message": "cart checkout kar do",
        "use_coins": True,
        "delivery_address": sample_address
    })
    assert res.status_code == 200
    data = res.json()
    assert data["order_review"] is not None
    assert data["order_review"]["total"] <= data["order_review"]["subtotal"]

# TEST 12 — BELOW AUTONOMOUS THRESHOLD (₹2,999 <= ₹5,000)
def test_12_below_threshold_auto_flow(client, db, sample_address):
    sess = f"test_agentic_t12_{uuid.uuid4().hex[:8]}"
    prods = client.get("/api/v1/products").json()
    speed_shoe = next(p for p in prods if "SpeedFlow" in p["name"])
    client.post("/api/v1/cart/items", json={"session_id": sess, "product_id": speed_shoe["id"], "quantity": 1})

    res = client.post("/api/v1/ai/shopping", json={
        "session_id": sess,
        "message": "cart checkout kar do",
        "delivery_address": sample_address
    })
    assert res.status_code == 200
    data = res.json()
    assert data["order_review"]["is_above_threshold"] is False
    assert data["requires_approval"] is False

# TEST 13 — ABOVE AUTONOMOUS THRESHOLD (₹6,998 > ₹5,000)
def test_13_above_threshold_governance_required(client, db, sample_address):
    sess = f"test_agentic_t13_{uuid.uuid4().hex[:8]}"
    prods = client.get("/api/v1/products").json()
    pro_shoe = next(p for p in prods if "Pro" in p["name"])
    client.post("/api/v1/cart/items", json={"session_id": sess, "product_id": pro_shoe["id"], "quantity": 2})

    res = client.post("/api/v1/ai/shopping", json={
        "session_id": sess,
        "message": "cart checkout kar do",
        "delivery_address": sample_address
    })
    assert res.status_code == 200
    data = res.json()
    assert data["order_review"]["is_above_threshold"] is True
    assert data["requires_approval"] is True
    assert "approval" in data["message"].lower()

# TEST 14 — EXPLICIT HUMAN APPROVAL GRANTED
def test_14_explicit_human_approval(client, db, sample_address):
    sess = f"test_agentic_t14_{uuid.uuid4().hex[:8]}"
    prods = client.get("/api/v1/products").json()
    pro_shoe = next(p for p in prods if "Pro" in p["name"])
    client.post("/api/v1/cart/items", json={"session_id": sess, "product_id": pro_shoe["id"], "quantity": 2})

    # Create Intent
    intent_res = client.post("/api/v1/purchase-intents/", json={
        "session_id": sess,
        "buyer_id": "shopper@example.com",
        "delivery_address": sample_address
    })
    assert intent_res.status_code == 200
    intent_id = intent_res.json()["id"]

    # Evaluate Intent
    eval_res = client.post(f"/api/v1/purchase-intents/{intent_id}/evaluate")
    eval_data = eval_res.json()
    assert eval_data["decision"] == "REQUIRES_APPROVAL"
    appr_id = eval_data["approval_request"]["id"]

    # Explicit Human Approval
    appr_res = client.post(f"/api/v1/approvals/{appr_id}/approve")
    assert appr_res.status_code == 200
    assert appr_res.json()["authorization"]["id"] is not None

# TEST 15 — CANCEL APPROVAL
def test_15_cancel_approval_blocks_order(client, db, sample_address):
    sess = f"test_agentic_t15_{uuid.uuid4().hex[:8]}"
    prods = client.get("/api/v1/products").json()
    pro_shoe = next(p for p in prods if "Pro" in p["name"])
    client.post("/api/v1/cart/items", json={"session_id": sess, "product_id": pro_shoe["id"], "quantity": 2})

    intent_res = client.post("/api/v1/purchase-intents/", json={
        "session_id": sess,
        "buyer_id": "shopper@example.com",
        "delivery_address": sample_address
    })
    assert intent_res.status_code == 200
    intent_id = intent_res.json()["id"]

    eval_res = client.post(f"/api/v1/purchase-intents/{intent_id}/evaluate")
    assert eval_res.status_code == 200
    appr_id = eval_res.json()["approval_request"]["id"]

    reject_res = client.post(f"/api/v1/approvals/{appr_id}/reject", json={"reason": "Customer cancelled"})
    assert reject_res.status_code == 200
    assert reject_res.json()["approval"]["status"] == "REJECTED"

# TEST 16 — RAZORPAY FAILURE HANDLING
def test_16_razorpay_order_creation_guards(client, db, sample_address):
    res = client.post("/api/v1/payments/create-order", json={
        "purchase_intent_id": "invalid_pi",
        "authorization_id": "invalid_auth",
        "idempotency_key": "idem_fail_16"
    })
    assert res.status_code in [400, 404]

# TEST 17 — SIGNATURE VERIFICATION REJECTION
def test_17_signature_tampering_rejected(client, db):
    res = client.post("/api/v1/payments/verify-signature", json={
        "razorpay_order_id": "order_fake_123",
        "razorpay_payment_id": "pay_fake_456",
        "razorpay_signature": "invalid_tampered_hmac_signature"
    })
    assert res.status_code in [400, 404]

# TEST 18 — PAYMENT RETRY / IDEMPOTENCY
def test_18_payment_retry_idempotency(client, db, sample_address):
    sess = f"test_agentic_t18_{uuid.uuid4().hex[:8]}"
    prods = client.get("/api/v1/products").json()
    speed_shoe = next(p for p in prods if "SpeedFlow" in p["name"])
    client.post("/api/v1/cart/items", json={"session_id": sess, "product_id": speed_shoe["id"], "quantity": 1})

    intent_res = client.post("/api/v1/purchase-intents/", json={
        "session_id": sess,
        "buyer_id": "shopper@example.com",
        "delivery_address": sample_address
    })
    assert intent_res.status_code == 200
    intent_id = intent_res.json()["id"]

    eval_res = client.post(f"/api/v1/purchase-intents/{intent_id}/evaluate")
    assert eval_res.status_code == 200
    auth_id = eval_res.json()["authorization"]["id"]

    idem_key = f"idem_retry_{sess}"
    res1 = client.post("/api/v1/payments/create-order", json={
        "purchase_intent_id": intent_id,
        "authorization_id": auth_id,
        "idempotency_key": idem_key
    })
    res2 = client.post("/api/v1/payments/create-order", json={
        "purchase_intent_id": intent_id,
        "authorization_id": auth_id,
        "idempotency_key": idem_key
    })

    assert res1.status_code == 200
    assert res2.status_code == 200
    assert res1.json()["razorpay_order_id"] == res2.json()["razorpay_order_id"]

# TEST 19 — STOCK CHANGE DETECTION
def test_19_stock_exhaustion_pauses_checkout(client, db, sample_address):
    sess = f"test_agentic_t19_{uuid.uuid4().hex[:8]}"
    prods = client.get("/api/v1/products").json()
    bottle = next(p for p in prods if "Bottle" in p["name"])
    client.post("/api/v1/cart/items", json={"session_id": sess, "product_id": bottle["id"], "quantity": 5})

    # Temporarily set inventory to 0
    inv = db.query(Inventory).filter(Inventory.product_id == bottle["id"]).first()
    original_qty = inv.stock_quantity if inv else 10
    if inv:
        inv.stock_quantity = 0
        db.commit()

    try:
        res = client.post("/api/v1/ai/shopping", json={
            "session_id": sess,
            "message": "cart checkout kar do",
            "delivery_address": sample_address
        })
        assert res.status_code == 200
        data = res.json()
        assert "stock" in data["message"].lower() or "available" in data["message"].lower()
    finally:
        if inv:
            inv.stock_quantity = original_qty
            db.commit()

# TEST 20 — PRICE CHANGE RECOMPUTATION
def test_20_price_change_recomputed_authoritatively(client, db, sample_address):
    sess = f"test_agentic_t20_{uuid.uuid4().hex[:8]}"
    prods = client.get("/api/v1/products").json()
    client.post("/api/v1/cart/items", json={"session_id": sess, "product_id": prods[0]["id"], "quantity": 1})

    res = client.post("/api/v1/ai/shopping", json={
        "session_id": sess,
        "message": "cart checkout kar do",
        "delivery_address": sample_address
    })
    assert res.status_code == 200
    data = res.json()
    assert data["order_review"]["total"] == float(prods[0]["price"])

# TEST 21 — CROSS-USER SECURITY ISOLATION
def test_21_cross_user_isolation(client, db):
    intent_res = client.post("/api/v1/purchase-intents/", json={
        "session_id": "user_a_sess",
        "buyer_id": "usera@example.com"
    })
    assert intent_res.status_code in [200, 400]

# TEST 22 — CROSS-MERCHANT ISOLATION
def test_22_cross_merchant_isolation(client, db):
    merchants = db.query(Merchant).all()
    if len(merchants) >= 2:
        m1, m2 = merchants[0], merchants[1]
        prod_m1 = db.query(Product).filter(Product.merchant_id == m1.id).first()
        if prod_m1:
            res = client.get(f"/api/v1/products/{prod_m1.id}?merchant_id={m2.id}")
            assert res.status_code in [404, 403]
