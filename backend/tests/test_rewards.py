import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.user import User
from app.database.models.rewards import Coupon, Voucher, UserVoucher, CoinWallet, CoinLedger, RewardPointsWallet
from app.database.models.payment_transaction import PaymentTransaction
from app.tools.shopping_tools import add_to_cart
from app.services.reward_service import RewardService

def test_public_coupons_retrieval(client: TestClient, setup_test_data):
    m1_id = setup_test_data["m1"]
    res = client.get(f"/api/v1/rewards/coupons?merchant_id={m1_id}")
    assert res.status_code == 200
    coupons = res.json()
    assert len(coupons) >= 3
    codes = [c["code"] for c in coupons]
    assert "SAVE500" in codes
    assert "APEX10" in codes
    assert "WELCOME200" in codes

def test_coupon_validation_and_authoritative_discount(client: TestClient, db: Session, setup_test_data):
    m1_id = setup_test_data["m1"]
    
    # 1. Product setup: Shoes ₹3,499
    p = Product(merchant_id=m1_id, name="Performance Trail Shoes", price=Decimal("3499.00"), category="Running", is_active=True)
    db.add(p)
    db.flush()
    db.add(Inventory(merchant_id=m1_id, product_id=p.id, stock_quantity=10))
    db.commit()

    sess_id = "sess_coupon_test_01"
    add_to_cart(db=db, merchant_id=m1_id, session_id=sess_id, product_id=p.id, quantity=1)

    # 2. Test valid coupon SAVE500 on ₹3,499 (Min: ₹2,500) -> Discount ₹500 -> Total ₹2,999
    res = client.post("/api/v1/rewards/calculate-pricing", json={
        "session_id": sess_id,
        "coupon_code": "SAVE500"
    })
    assert res.status_code == 200
    data = res.json()
    assert float(data["subtotal"]) == 3499.0
    assert float(data["coupon_discount"]) == 500.0
    assert float(data["total"]) == 2999.0
    assert data["points_to_earn"] == 29 # 1 point per ₹100 on ₹2,999

def test_coupon_min_order_validation(client: TestClient, db: Session, setup_test_data):
    m1_id = setup_test_data["m1"]
    
    # Socks ₹399 (Below SAVE500 min ₹2,500)
    p = Product(merchant_id=m1_id, name="Performance Socks", price=Decimal("399.00"), category="Accessories", is_active=True)
    db.add(p)
    db.flush()
    db.add(Inventory(merchant_id=m1_id, product_id=p.id, stock_quantity=20))
    db.commit()

    sess_id = "sess_coupon_min_test"
    add_to_cart(db=db, merchant_id=m1_id, session_id=sess_id, product_id=p.id, quantity=1)

    res = client.post("/api/v1/rewards/calculate-pricing", json={
        "session_id": sess_id,
        "coupon_code": "SAVE500"
    })
    assert res.status_code == 400
    assert "Minimum order value" in res.json()["detail"]

def test_expired_coupon_rejected(client: TestClient, db: Session, setup_test_data):
    m1_id = setup_test_data["m1"]
    
    # Add expired coupon
    past_date = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=5)
    exp_coupon = Coupon(
        merchant_id=m1_id,
        code="EXPIRED50",
        description="Expired deal",
        discount_type="FIXED",
        discount_value=Decimal("50.00"),
        min_cart_amount=Decimal("100.00"),
        expires_at=past_date,
        is_active=True
    )
    db.add(exp_coupon)
    db.commit()

    sess_id = "sess_exp_coup"
    p = Product(merchant_id=m1_id, name="Exp Test Prod", price=Decimal("1000.00"), category="Gear", is_active=True)
    db.add(p)
    db.flush()
    db.add(Inventory(merchant_id=m1_id, product_id=p.id, stock_quantity=10))
    db.commit()
    add_to_cart(db=db, merchant_id=m1_id, session_id=sess_id, product_id=p.id, quantity=1)

    res = client.post("/api/v1/rewards/calculate-pricing", json={
        "session_id": sess_id,
        "coupon_code": "EXPIRED50"
    })
    assert res.status_code == 400
    assert "expired" in res.json()["detail"].lower()

def test_coin_balance_and_redemption(client: TestClient, db: Session, setup_test_data):
    m1_id = setup_test_data["m1"]
    
    # Customer registration
    login_res = client.post("/api/v1/auth/register", json={
        "email": "coin_user@example.com",
        "password": "password123",
        "full_name": "Coin User"
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch rewards summary -> verifies starter 1,250 coins & 150 points
    rew_res = client.get("/api/v1/rewards/me", headers=headers)
    assert rew_res.status_code == 200
    rew_data = rew_res.json()
    assert rew_data["coin_balance"] >= 1250
    assert rew_data["points_balance"] >= 150
    assert float(rew_data["estimated_coin_value_inr"]) >= 125.0

    # Add item ₹3,499
    p = Product(merchant_id=m1_id, name="Marathon Runner", price=Decimal("3499.00"), category="Running", is_active=True)
    db.add(p)
    db.flush()
    db.add(Inventory(merchant_id=m1_id, product_id=p.id, stock_quantity=10))
    db.commit()

    sess_id = "sess_coin_redeem"
    add_to_cart(db=db, merchant_id=m1_id, session_id=sess_id, product_id=p.id, quantity=1)

    # Calculate pricing with 500 coins redemption (500 coins = ₹50.00 discount)
    res = client.post(
        "/api/v1/rewards/calculate-pricing",
        json={"session_id": sess_id, "use_coins": True, "coins_to_redeem": 500},
        headers=headers
    )
    assert res.status_code == 200
    calc = res.json()
    assert calc["coins_used"] == 500
    assert float(calc["coin_discount"]) == 50.0
    assert float(calc["total"]) == 3449.0 # 3499 - 50

def test_reward_points_awarded_idempotently_after_payment(client: TestClient, db: Session, setup_test_data):
    m1_id = setup_test_data["m1"]
    
    # Customer registration
    reg_res = client.post("/api/v1/auth/register", json={
        "email": "loyalty_shopper@example.com",
        "password": "password123",
        "full_name": "Loyalty Shopper"
    })
    token = reg_res.json()["access_token"]
    user_id = reg_res.json()["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}

    # Initial points
    init_rew = client.get("/api/v1/rewards/me", headers=headers).json()
    initial_points = init_rew["points_balance"]

    p = Product(merchant_id=m1_id, name="Gold Track Shoes", price=Decimal("3000.00"), category="Running", is_active=True)
    db.add(p)
    db.flush()
    db.add(Inventory(merchant_id=m1_id, product_id=p.id, stock_quantity=10))
    db.commit()

    sess_id = "sess_loyalty_order"
    add_to_cart(db=db, merchant_id=m1_id, session_id=sess_id, product_id=p.id, quantity=1)

    # Create Purchase Intent with SAVE500 (₹3,000 - ₹500 = ₹2,500 -> 25 points earned)
    intent_res = client.post("/api/v1/purchase-intents/", json={
        "session_id": sess_id,
        "buyer_id": "loyalty_shopper@example.com",
        "merchant_id": m1_id,
        "coupon_code": "SAVE500",
        "delivery_address": {"full_name": "Loyalty Shopper", "phone": "9876543210", "email": "loyalty_shopper@example.com", "address_line1": "Road 1", "city": "City", "state": "State", "pin_code": "560001", "country": "India"}
    })
    assert intent_res.status_code == 200
    intent_id = intent_res.json()["id"]
    assert Decimal(str(intent_res.json()["requested_amount"])) == Decimal("2500.00")

    # Evaluate & Create Order
    eval_res = client.post(f"/api/v1/purchase-intents/{intent_id}/evaluate")
    auth_id = eval_res.json()["authorization"]["id"]

    order_res = client.post("/api/v1/payments/create-order", json={
        "purchase_intent_id": intent_id,
        "authorization_id": auth_id,
        "idempotency_key": "idemp_loyalty_order_01"
    })
    tx_id = order_res.json()["payment_transaction_id"]

    # Verify points NOT yet awarded before payment
    mid_rew = client.get("/api/v1/rewards/me", headers=headers).json()
    assert mid_rew["points_balance"] == initial_points

    # Complete payment verification
    sig_res = client.post("/api/v1/payments/verify-signature", json={
        "razorpay_order_id": order_res.json()["razorpay_order_id"] or "order_mock_loyalty",
        "razorpay_payment_id": "pay_mock_loyalty_123",
        "razorpay_signature": "sig_mock_valid"
    })
    assert sig_res.status_code == 200

    # Verify points awarded: +25 points
    final_rew = client.get("/api/v1/rewards/me", headers=headers).json()
    assert final_rew["points_balance"] == initial_points + 25

    # Test Idempotency: Triggering post-payment again should NOT award duplicate points
    RewardService.apply_post_payment_rewards(
        db=db,
        merchant_id=m1_id,
        user_id=user_id,
        order_reference=intent_id[:8].upper(),
        payment_transaction_id=tx_id,
        pricing_data={"points_to_earn": 25}
    )
    dup_rew = client.get("/api/v1/rewards/me", headers=headers).json()
    assert dup_rew["points_balance"] == initial_points + 25
