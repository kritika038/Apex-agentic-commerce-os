import pytest
from decimal import Decimal
from fastapi.testclient import TestClient

from app.main import app
from app.database.session import get_db, SessionLocal
from app.database.models.merchant import Merchant
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.policy import Policy
from app.database.models.cart import Cart, CartItem
from app.database.models.purchase_intent import PurchaseIntent
from app.database.models.transaction_authorization import TransactionAuthorization
from app.database.models.payment_transaction import PaymentTransaction
from app.agents.shopping_agent import ShoppingAgent
from app.agents.intent_engine import ConversationIntentEngine

client = TestClient(app)

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_1_conversational_discovery_selection_and_finalize_single_product(db_session):
    """
    Validates Turn 1: "Running shoes under 5000"
    Turn 2: "Which one is best?"
    Turn 3: "Finalize this shoe and order it"
    Ensures:
    - Candidate products are discovered
    - Best product is selected
    - Finalize resolves strictly to selected product
    - Quantity defaults to 1
    - Order total is ₹2,999.00 (NOT inflated by other candidates)
    """
    merchant = db_session.query(Merchant).filter(Merchant.is_active == True).first()
    assert merchant is not None
    _ensure_products_seeded(db_session, merchant.id)

    session_id = "test_sess_finalize_single_001"
    agent = ShoppingAgent(
        db=db_session,
        merchant_id=merchant.id,
        session_id=session_id,
        delivery_address={
            "full_name": "Rohan Verma",
            "phone": "9876543210",
            "email": "rohan@example.com",
            "address_line1": "123 Marine Drive",
            "city": "Mumbai",
            "state": "Maharashtra",
            "pin_code": "400020"
        }
    )

    # Turn 1: Search
    res1 = agent.process_message("Running shoes under 5000")
    assert res1.products is not None
    assert len(res1.products) >= 1

    # Turn 2: Which one is best
    res2 = agent.process_message("Which one is best?")
    assert len(res2.products) == 1
    selected_shoe = res2.products[0]
    assert selected_shoe["name"] in ["SpeedFlow Marathon Shoes", "Pro Running Shoes", "Air Cushion Trail Running Shoes"]

    # Turn 3: Finalize this shoe and order it
    res3 = agent.process_message("Finalize this shoe and order it")
    assert res3.order_review is not None
    assert len(res3.order_review.items) == 1
    item = res3.order_review.items[0]
    assert item.product_id == selected_shoe["id"]
    assert item.quantity == 1
    assert item.price == selected_shoe["price"]
    assert res3.order_review.total == selected_shoe["price"]

def test_2_explicit_quantity_preserved_on_finalize(db_session):
    """
    Validates that explicit quantity 'buy 2' or 'order 2' is respected.
    """
    merchant = db_session.query(Merchant).filter(Merchant.is_active == True).first()
    session_id = "test_sess_qty_2_002"
    agent = ShoppingAgent(
        db=db_session,
        merchant_id=merchant.id,
        session_id=session_id,
        delivery_address={
            "full_name": "Rohan Verma",
            "phone": "9876543210",
            "email": "rohan@example.com",
            "address_line1": "123 Marine Drive",
            "city": "Mumbai",
            "state": "Maharashtra",
            "pin_code": "400020"
        }
    )

    # Search & Select
    agent.process_message("Performance Socks")
    res = agent.process_message("Finalize 2 pairs and order it")
    assert res.order_review is not None
    assert len(res.order_review.items) == 1
    assert res.order_review.items[0].quantity == 2

def test_3_pre_existing_cart_items_isolated_from_direct_product_finalize(db_session):
    """
    Ensures that if the cart had 5 items previously,
    saying 'Finalize this shoe and order it' isolates the purchase
    to the single shoe and does not inflate to 6 items or ₹14,894.
    """
    merchant = db_session.query(Merchant).filter(Merchant.is_active == True).first()
    session_id = "test_sess_isolate_cart_003"

    # Pre-populate cart with 5 dummy items
    cart = Cart(session_id=session_id, merchant_id=merchant.id)
    db_session.add(cart)
    db_session.commit()

    products = db_session.query(Product).filter(Product.merchant_id == merchant.id).limit(5).all()
    for p in products:
        db_session.add(CartItem(
            cart_id=cart.id,
            product_id=p.id,
            quantity=1,
            unit_price_snapshot=p.price
        ))
    db_session.commit()

    # Now agent processes "Finalize this shoe and order it"
    agent = ShoppingAgent(
        db=db_session,
        merchant_id=merchant.id,
        session_id=session_id,
        delivery_address={
            "full_name": "Rohan Verma",
            "phone": "9876543210",
            "email": "rohan@example.com",
            "address_line1": "123 Marine Drive",
            "city": "Mumbai",
            "state": "Maharashtra",
            "pin_code": "400020"
        }
    )

    # Discover & select shoe
    agent.process_message("Running shoes under 5000")
    agent.process_message("Which one is best?")
    res = agent.process_message("Finalize this shoe and order it")

    assert res.order_review is not None
    # Must contain strictly 1 item (the selected shoe), NOT 6 items
    assert len(res.order_review.items) == 1
    assert res.order_review.total < 5000.0

def test_4_high_value_transaction_triggers_requires_approval(db_session):
    """
    Validates that a purchase > ₹5,000 triggers REQUIRES_APPROVAL (APPROVAL_REQUIRED)
    and is NOT treated as a payment failure.
    """
    merchant = db_session.query(Merchant).filter(Merchant.is_active == True).first()
    session_id = "test_sess_approval_004"

    # Create high value cart
    cart = Cart(session_id=session_id, merchant_id=merchant.id)
    db_session.add(cart)
    db_session.commit()

    prod = db_session.query(Product).filter(Product.merchant_id == merchant.id).first()
    # Add quantity to exceed 5000 threshold
    db_session.add(CartItem(
        cart_id=cart.id,
        product_id=prod.id,
        quantity=3,
        unit_price_snapshot=Decimal("2999.00")
    ))
    db_session.commit()

    # Step 1: Create Purchase Intent
    intent_res = client.post("/api/v1/purchase-intents/", json={
        "session_id": session_id,
        "buyer_id": "shopper@example.com",
        "delivery_address": {
            "full_name": "Rohan Verma",
            "phone": "9876543210",
            "email": "rohan@example.com",
            "address_line1": "123 Marine Drive",
            "city": "Mumbai",
            "state": "Maharashtra",
            "pin_code": "400020"
        }
    })
    assert intent_res.status_code == 200
    intent_id = intent_res.json()["id"]

    # Step 2: Evaluate Intent -> REQUIRES_APPROVAL
    eval_res = client.post(f"/api/v1/purchase-intents/{intent_id}/evaluate")
    assert eval_res.status_code == 200
    eval_data = eval_res.json()
    assert eval_data["decision"] == "REQUIRES_APPROVAL"
    assert eval_data["approval_request"] is not None

def test_5_hard_policy_violation_triggers_policy_blocked(db_session):
    """
    Validates that a transaction exceeding max transaction limit (> ₹10,000)
    or max item quantity (> 5) triggers BLOCK (POLICY_BLOCKED).
    """
    merchant = db_session.query(Merchant).filter(Merchant.is_active == True).first()
    session_id = "test_sess_block_005"

    cart = Cart(session_id=session_id, merchant_id=merchant.id)
    db_session.add(cart)
    db_session.commit()

    prod = db_session.query(Product).filter(Product.merchant_id == merchant.id).first()
    if prod.inventory:
        prod.inventory.stock_quantity = 50
    db_session.commit()

    # Add 6 items (exceeds max item limit of 5 and max transaction limit of 10000)
    db_session.add(CartItem(
        cart_id=cart.id,
        product_id=prod.id,
        quantity=6,
        unit_price_snapshot=Decimal("2999.00")
    ))
    db_session.commit()

    intent_res = client.post("/api/v1/purchase-intents/", json={
        "session_id": session_id,
        "buyer_id": "shopper@example.com",
        "delivery_address": {
            "full_name": "Rohan Verma",
            "phone": "9876543210",
            "email": "rohan@example.com",
            "address_line1": "123 Marine Drive",
            "city": "Mumbai",
            "state": "Maharashtra",
            "pin_code": "400020"
        }
    })
    assert intent_res.status_code == 200
    intent_id = intent_res.json()["id"]

    eval_res = client.post(f"/api/v1/purchase-intents/{intent_id}/evaluate")
    assert eval_res.status_code == 200
    eval_data = eval_res.json()
    assert eval_data["decision"] in ["DENY", "BLOCK"]
    assert len(eval_data.get("violations", [])) > 0

def test_6_hinglish_and_hindi_entity_resolution_and_finalize(db_session):
    """
    Validates Hinglish/Hindi multi-turn purchase:
    Turn 1: "Paanch hazaar ke andar running joote"
    Turn 2: "Sabse accha wala konsa hai?"
    Turn 3: "Ye wala shoe final karo aur order kar do"
    """
    merchant = db_session.query(Merchant).filter(Merchant.is_active == True).first()
    session_id = "test_sess_hinglish_006"

    agent = ShoppingAgent(
        db=db_session,
        merchant_id=merchant.id,
        session_id=session_id,
        delivery_address={
            "full_name": "Aakash Gupta",
            "phone": "9876543210",
            "email": "aakash@example.com",
            "address_line1": "456 Connaught Place",
            "city": "New Delhi",
            "state": "Delhi",
            "pin_code": "110001"
        }
    )

    # Turn 1
    res1 = agent.process_message("Paanch hazaar ke andar running joote")
    assert len(res1.products) >= 1

    # Turn 2
    res2 = agent.process_message("Sabse accha wala konsa hai?")
    assert len(res2.products) == 1
    best_prod = res2.products[0]

    # Turn 3
    res3 = agent.process_message("Ye wala shoe final karo aur order kar do")
    assert res3.order_review is not None
    assert len(res3.order_review.items) == 1
    assert res3.order_review.items[0].product_id == best_prod["id"]
    assert res3.order_review.items[0].quantity == 1

def test_7_payment_failed_state_on_signature_mismatch(db_session):
    """
    Validates that actual gateway / signature verification failures
    return HTTP 400/404 and fail the transaction safely.
    """
    verify_res = client.post("/api/v1/payments/verify-signature", json={
        "razorpay_order_id": "order_invalid_12345",
        "razorpay_payment_id": "pay_invalid_67890",
        "razorpay_signature": "invalid_signature_hash"
    })
    assert verify_res.status_code in [400, 404]

def _ensure_products_seeded(db, merchant_id):
    speedflow = db.query(Product).filter(Product.merchant_id == merchant_id, Product.name.ilike("%SpeedFlow%")).first()
    if not speedflow:
        speedflow = Product(
            merchant_id=merchant_id,
            name="SpeedFlow Marathon Shoes",
            description="Ultra-light marathon racing shoe",
            price=Decimal("2999.00"),
            category="Footwear",
            currency="INR",
            is_active=True
        )
        db.add(speedflow)
        db.flush()
    inv1 = db.query(Inventory).filter(Inventory.product_id == speedflow.id, Inventory.merchant_id == merchant_id).first()
    if not inv1:
        db.add(Inventory(merchant_id=merchant_id, product_id=speedflow.id, stock_quantity=50, reserved_quantity=0))
    elif inv1.stock_quantity <= 0:
        inv1.stock_quantity = 50

    pro_running = db.query(Product).filter(Product.merchant_id == merchant_id, Product.name.ilike("%Pro Running%")).first()
    if not pro_running:
        pro_running = Product(
            merchant_id=merchant_id,
            name="Pro Running Shoes",
            description="Responsive cushioning shoe",
            price=Decimal("3499.00"),
            category="Footwear",
            currency="INR",
            is_active=True
        )
        db.add(pro_running)
        db.flush()
    inv2 = db.query(Inventory).filter(Inventory.product_id == pro_running.id, Inventory.merchant_id == merchant_id).first()
    if not inv2:
        db.add(Inventory(merchant_id=merchant_id, product_id=pro_running.id, stock_quantity=50, reserved_quantity=0))
    elif inv2.stock_quantity <= 0:
        inv2.stock_quantity = 50

    trail = db.query(Product).filter(Product.merchant_id == merchant_id, Product.name.ilike("%Air Cushion Trail%")).first()
    if not trail:
        trail = Product(
            merchant_id=merchant_id,
            name="Air Cushion Trail Running Shoes",
            description="All-terrain trail running shoes",
            price=Decimal("4299.00"),
            category="Footwear",
            currency="INR",
            is_active=True
        )
        db.add(trail)
        db.flush()
    inv3 = db.query(Inventory).filter(Inventory.product_id == trail.id, Inventory.merchant_id == merchant_id).first()
    if not inv3:
        db.add(Inventory(merchant_id=merchant_id, product_id=trail.id, stock_quantity=50, reserved_quantity=0))
    elif inv3.stock_quantity <= 0:
        inv3.stock_quantity = 50

    db.commit()
    return speedflow, pro_running, trail

def test_scenario_a_speedflow_marathon_single_purchase(db_session):
    """
    TEST A:
    User searches 'running shoes under 5k' -> selects SpeedFlow Marathon Shoes ₹2,999 -> 'finalize this shoe'
    Expected: 1 x SpeedFlow Marathon Shoes = ₹2,999 (No other products).
    """
    merchant = db_session.query(Merchant).filter(Merchant.is_active == True).first()
    _ensure_products_seeded(db_session, merchant.id)

    agent = ShoppingAgent(
        db=db_session,
        merchant_id=merchant.id,
        session_id="test_scenario_a_sess",
        delivery_address={
            "full_name": "Test User", "phone": "9999999999", "address_line1": "123 Street",
            "city": "Bengaluru", "state": "Karnataka", "pin_code": "560001"
        }
    )

    agent.process_message("running shoes under 5k")
    agent.process_message("Which one is SpeedFlow Marathon Shoes?")
    res = agent.process_message("finalize this shoe")

    assert res.order_review is not None
    assert len(res.order_review.items) == 1
    assert "SpeedFlow" in res.order_review.items[0].name
    assert res.order_review.items[0].quantity == 1
    assert res.order_review.total == 2999.0
    assert res.order_review.is_above_threshold is False

def test_scenario_b_pro_running_single_purchase(db_session):
    """
    TEST B:
    User searches 'running shoes under 5k' -> selects Pro Running Shoes ₹3,499 -> 'buy this one'
    Expected: 1 x Pro Running Shoes = ₹3,499.
    """
    merchant = db_session.query(Merchant).filter(Merchant.is_active == True).first()
    _ensure_products_seeded(db_session, merchant.id)

    agent = ShoppingAgent(
        db=db_session,
        merchant_id=merchant.id,
        session_id="test_scenario_b_sess",
        delivery_address={
            "full_name": "Test User", "phone": "9999999999", "address_line1": "123 Street",
            "city": "Bengaluru", "state": "Karnataka", "pin_code": "560001"
        }
    )

    agent.process_message("running shoes under 5k")
    agent.process_message("Show me Pro Running Shoes")
    res = agent.process_message("buy this one")

    assert res.order_review is not None
    assert len(res.order_review.items) == 1
    assert "Pro Running" in res.order_review.items[0].name
    assert res.order_review.items[0].quantity == 1
    assert res.order_review.total == 3499.0
    assert res.order_review.is_above_threshold is False

def test_scenario_c_buy_2_pro_running_shoes_triggers_approval(db_session):
    """
    TEST C:
    User says 'buy 2 Pro Running Shoes'
    Expected: 2 x Pro Running Shoes = ₹6,998 -> APPROVAL_REQUIRED (> ₹5,000).
    """
    merchant = db_session.query(Merchant).filter(Merchant.is_active == True).first()
    _ensure_products_seeded(db_session, merchant.id)

    agent = ShoppingAgent(
        db=db_session,
        merchant_id=merchant.id,
        session_id="test_scenario_c_sess",
        delivery_address={
            "full_name": "Test User", "phone": "9999999999", "address_line1": "123 Street",
            "city": "Bengaluru", "state": "Karnataka", "pin_code": "560001"
        }
    )

    res = agent.process_message("buy 2 Pro Running Shoes")
    assert res.order_review is not None
    assert len(res.order_review.items) == 1
    assert res.order_review.items[0].quantity == 2
    assert res.order_review.total == 6998.0
    assert res.order_review.is_above_threshold is True
    assert "APPROVAL_REQUIRED" in res.actions

def test_scenario_d_stale_cart_isolated_from_direct_purchase(db_session):
    """
    TEST D:
    User has multiple items in cart. Then explicitly selects one product and says 'finalize this'.
    Expected: Only the selected product is purchased.
    """
    merchant = db_session.query(Merchant).filter(Merchant.is_active == True).first()
    speedflow, pro_running, trail = _ensure_products_seeded(db_session, merchant.id)

    sess_id = "test_scenario_d_sess"
    cart = Cart(session_id=sess_id, merchant_id=merchant.id)
    db_session.add(cart)
    db_session.commit()

    db_session.add(CartItem(cart_id=cart.id, product_id=speedflow.id, quantity=1, unit_price_snapshot=speedflow.price))
    db_session.add(CartItem(cart_id=cart.id, product_id=pro_running.id, quantity=1, unit_price_snapshot=pro_running.price))
    db_session.add(CartItem(cart_id=cart.id, product_id=trail.id, quantity=1, unit_price_snapshot=trail.price))
    db_session.commit()

    agent = ShoppingAgent(
        db=db_session,
        merchant_id=merchant.id,
        session_id=sess_id,
        delivery_address={
            "full_name": "Test User", "phone": "9999999999", "address_line1": "123 Street",
            "city": "Bengaluru", "state": "Karnataka", "pin_code": "560001"
        }
    )

    agent.process_message("Show me SpeedFlow Marathon Shoes")
    res = agent.process_message("finalize this shoe")

    assert res.order_review is not None
    assert len(res.order_review.items) == 1
    assert res.order_review.items[0].product_id == speedflow.id
    assert res.order_review.total == float(speedflow.price)

def test_scenario_e_checkout_my_cart_includes_all_items(db_session):
    """
    TEST E:
    User says 'checkout my cart'.
    Expected: Cart items are included.
    """
    merchant = db_session.query(Merchant).filter(Merchant.is_active == True).first()
    speedflow, pro_running, _ = _ensure_products_seeded(db_session, merchant.id)

    sess_id = "test_scenario_e_sess"
    cart = Cart(session_id=sess_id, merchant_id=merchant.id)
    db_session.add(cart)
    db_session.commit()

    db_session.add(CartItem(cart_id=cart.id, product_id=speedflow.id, quantity=1, unit_price_snapshot=speedflow.price))
    db_session.add(CartItem(cart_id=cart.id, product_id=pro_running.id, quantity=1, unit_price_snapshot=pro_running.price))
    db_session.commit()

    agent = ShoppingAgent(
        db=db_session,
        merchant_id=merchant.id,
        session_id=sess_id,
        delivery_address={
            "full_name": "Test User", "phone": "9999999999", "address_line1": "123 Street",
            "city": "Bengaluru", "state": "Karnataka", "pin_code": "560001"
        }
    )

    res = agent.process_message("checkout my cart")
    assert res.order_review is not None
    assert len(res.order_review.items) == 2
    assert res.order_review.total == float(speedflow.price + pro_running.price)

def test_scenario_f_exact_5000_threshold_not_approval_required(db_session):
    """
    TEST F:
    ₹5,000 exactly -> NOT approval-required because threshold is exceeded only when > ₹5,000.
    """
    from app.policies.policy_engine import PolicyEngine
    merchant = db_session.query(Merchant).filter(Merchant.is_active == True).first()
    
    cart = Cart(session_id="sess_5k_exact", merchant_id=merchant.id)
    db_session.add(cart)
    db_session.commit()

    p5k = db_session.query(Product).filter(Product.merchant_id == merchant.id, Product.name == "Gym Bag Pro 5k").first()
    if not p5k:
        p5k = Product(
            merchant_id=merchant.id,
            name="Gym Bag Pro 5k",
            description="5000 bag",
            price=Decimal("5000.00"),
            category="Accessories",
            currency="INR",
            is_active=True
        )
        db_session.add(p5k)
        db_session.flush()
        db_session.add(Inventory(merchant_id=merchant.id, product_id=p5k.id, stock_quantity=10, reserved_quantity=0))
        db_session.commit()
    else:
        p5k.is_active = True
        db_session.commit()

    intent = PurchaseIntent(
        merchant_id=merchant.id,
        buyer_id="buyer_5k@test.com",
        session_id="sess_5k_exact",
        cart_id=cart.id,
        status="CREATED",
        requested_amount=Decimal("5000.00"),
        currency="INR",
        product_summary={"items": [{"product_id": p5k.id, "quantity": 1, "price": 5000.0}]}
    )
    db_session.add(intent)
    db_session.commit()

    eval_result = PolicyEngine.evaluate_purchase_intent(db=db_session, purchase_intent_id=intent.id, merchant_id=merchant.id)
    assert eval_result["decision"] == "ALLOW"
    assert eval_result["requires_human_approval"] is False

def test_scenario_g_5001_triggers_approval_required(db_session):
    """
    TEST G:
    ₹5,001 -> APPROVAL_REQUIRED (> ₹5,000).
    """
    from app.policies.policy_engine import PolicyEngine
    merchant = db_session.query(Merchant).filter(Merchant.is_active == True).first()
    
    cart = Cart(session_id="sess_5001", merchant_id=merchant.id)
    db_session.add(cart)
    db_session.commit()

    p5001 = db_session.query(Product).filter(Product.merchant_id == merchant.id, Product.name == "Special Running Watch 5001").first()
    if not p5001:
        p5001 = Product(
            merchant_id=merchant.id,
            name="Special Running Watch 5001",
            description="5001 watch",
            price=Decimal("5001.00"),
            category="Electronics",
            currency="INR",
            is_active=True
        )
        db_session.add(p5001)
        db_session.flush()
        db_session.add(Inventory(merchant_id=merchant.id, product_id=p5001.id, stock_quantity=10, reserved_quantity=0))
        db_session.commit()
    else:
        p5001.is_active = True
        db_session.commit()

    intent = PurchaseIntent(
        merchant_id=merchant.id,
        buyer_id="buyer_5001@test.com",
        session_id="sess_5001",
        cart_id=cart.id,
        status="CREATED",
        requested_amount=Decimal("5001.00"),
        currency="INR",
        product_summary={"items": [{"product_id": p5001.id, "quantity": 1, "price": 5001.0}]}
    )
    db_session.add(intent)
    db_session.commit()

    eval_result = PolicyEngine.evaluate_purchase_intent(db=db_session, purchase_intent_id=intent.id, merchant_id=merchant.id)
    assert eval_result["decision"] == "REQUIRES_APPROVAL"
    assert eval_result["requires_human_approval"] is True

def test_scenario_h_10001_triggers_policy_blocked(db_session):
    """
    TEST H:
    ₹10,001 -> POLICY_BLOCKED (DENY) because > max transaction limit of ₹10,000.
    """
    from app.policies.policy_engine import PolicyEngine
    merchant = db_session.query(Merchant).filter(Merchant.is_active == True).first()
    
    cart = Cart(session_id="sess_10001", merchant_id=merchant.id)
    db_session.add(cart)
    db_session.commit()

    p10k = db_session.query(Product).filter(Product.merchant_id == merchant.id, Product.name == "Pro Treadmill 10001").first()
    if not p10k:
        p10k = Product(
            merchant_id=merchant.id,
            name="Pro Treadmill 10001",
            description="10001 treadmill",
            price=Decimal("10001.00"),
            category="Equipment",
            currency="INR",
            is_active=True
        )
        db_session.add(p10k)
        db_session.flush()
        db_session.add(Inventory(merchant_id=merchant.id, product_id=p10k.id, stock_quantity=10, reserved_quantity=0))
        db_session.commit()

    intent = PurchaseIntent(
        merchant_id=merchant.id,
        buyer_id="buyer_10001@test.com",
        session_id="sess_10001",
        cart_id=cart.id,
        status="CREATED",
        requested_amount=Decimal("10001.00"),
        currency="INR",
        product_summary={"items": [{"product_id": p10k.id, "quantity": 1, "price": 10001.0}]}
    )
    db_session.add(intent)
    db_session.commit()

    eval_result = PolicyEngine.evaluate_purchase_intent(db=db_session, purchase_intent_id=intent.id, merchant_id=merchant.id)
    assert eval_result["decision"] == "DENY"
    assert any("exceeds maximum transaction limit" in v for v in eval_result.get("violations", []))

def test_scenario_i_quantity_6_triggers_policy_blocked(db_session):
    """
    TEST I:
    Quantity 6 -> POLICY_BLOCKED (DENY) because > max item quantity of 5.
    """
    from app.policies.policy_engine import PolicyEngine
    merchant = db_session.query(Merchant).filter(Merchant.is_active == True).first()
    speedflow, _, _ = _ensure_products_seeded(db_session, merchant.id)

    cart = Cart(session_id="sess_qty6", merchant_id=merchant.id)
    db_session.add(cart)
    db_session.commit()

    intent = PurchaseIntent(
        merchant_id=merchant.id,
        buyer_id="buyer_qty6@test.com",
        session_id="sess_qty6",
        cart_id=cart.id,
        status="CREATED",
        requested_amount=Decimal("17994.00"),
        currency="INR",
        product_summary={"items": [{"product_id": speedflow.id, "quantity": 6, "price": 2999.0}]}
    )
    db_session.add(intent)
    db_session.commit()

    eval_result = PolicyEngine.evaluate_purchase_intent(db=db_session, purchase_intent_id=intent.id, merchant_id=merchant.id)
    assert eval_result["decision"] == "DENY"
    assert any("exceeds maximum allowed quantity" in v for v in eval_result.get("violations", []))

def test_scenario_j_ai_recommends_3_buy_this_one_selects_single_product(db_session):
    """
    TEST J:
    AI recommends 3 products -> User says 'buy this one' -> Only the explicitly selected product.
    """
    merchant = db_session.query(Merchant).filter(Merchant.is_active == True).first()
    _ensure_products_seeded(db_session, merchant.id)

    agent = ShoppingAgent(
        db=db_session,
        merchant_id=merchant.id,
        session_id="test_scenario_j_sess",
        delivery_address={
            "full_name": "Test User", "phone": "9999999999", "address_line1": "123 Street",
            "city": "Bengaluru", "state": "Karnataka", "pin_code": "560001"
        }
    )

    s_res = agent.process_message("Show running shoes")
    assert len(s_res.products) >= 2

    res = agent.process_message("buy this one")
    assert res.order_review is not None
    assert len(res.order_review.items) == 1
    assert res.order_review.items[0].quantity == 1
    assert res.order_review.total in [2999.0, 3499.0, 4299.0]

