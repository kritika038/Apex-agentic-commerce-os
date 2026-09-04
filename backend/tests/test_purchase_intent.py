import pytest
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.cart import Cart, CartItem
from app.database.models.purchase_intent import PurchaseIntent
from app.tools.shopping_tools import add_to_cart

def test_purchase_intent_creation_valid_cart(client: TestClient, db: Session, setup_test_data):
    m1_id = setup_test_data["m1"]
    session_id = "sess_pi_001"

    # 1. Setup products: Shoes (3499) and Socks (399)
    p1 = Product(merchant_id=m1_id, name="Pro Running Shoes", price=Decimal("3499.00"), category="Running", is_active=True)
    p2 = Product(merchant_id=m1_id, name="Performance Socks", price=Decimal("399.00"), category="Accessories", is_active=True)
    db.add_all([p1, p2])
    db.flush()
    db.add(Inventory(merchant_id=m1_id, product_id=p1.id, stock_quantity=10))
    db.add(Inventory(merchant_id=m1_id, product_id=p2.id, stock_quantity=50))
    db.commit()

    # 2. Add both to cart
    add_to_cart(db=db, merchant_id=m1_id, session_id=session_id, product_id=p1.id, quantity=1)
    add_to_cart(db=db, merchant_id=m1_id, session_id=session_id, product_id=p2.id, quantity=1)

    # 3. Create Purchase Intent with buyer max_price = 4000
    payload = {
        "session_id": session_id,
        "buyer_id": "buyer_test_1",
        "merchant_id": m1_id,
        "constraints": {
            "max_price": 4000.0,
            "currency": "INR",
            "quantity": 2
        }
    }

    res = client.post("/api/v1/ai/purchase-intents", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "CREATED"
    assert Decimal(str(data["requested_amount"])) == Decimal("3898.00")
    assert data["currency"] == "INR"
    assert len(data["items"]) == 2
    assert data["expires_at"] is not None
    assert "id" in data

    # Verify database record
    pi_db = db.query(PurchaseIntent).filter(PurchaseIntent.id == data["id"]).first()
    assert pi_db is not None
    assert pi_db.status == "CREATED"
    assert Decimal(str(pi_db.requested_amount)) == Decimal("3898.00")

def test_purchase_intent_budget_violation(client: TestClient, db: Session, setup_test_data):
    m1_id = setup_test_data["m1"]
    session_id = "sess_pi_budget_fail"

    p1 = Product(merchant_id=m1_id, name="Pro Running Shoes", price=Decimal("3499.00"), category="Running", is_active=True)
    p2 = Product(merchant_id=m1_id, name="Performance Socks", price=Decimal("399.00"), category="Accessories", is_active=True)
    db.add_all([p1, p2])
    db.flush()
    db.add(Inventory(merchant_id=m1_id, product_id=p1.id, stock_quantity=10))
    db.add(Inventory(merchant_id=m1_id, product_id=p2.id, stock_quantity=50))
    db.commit()

    add_to_cart(db=db, merchant_id=m1_id, session_id=session_id, product_id=p1.id, quantity=1)
    add_to_cart(db=db, merchant_id=m1_id, session_id=session_id, product_id=p2.id, quantity=1)

    # Buyer max_price is 3500, but total is 3898
    payload = {
        "session_id": session_id,
        "buyer_id": "buyer_low_budget",
        "merchant_id": m1_id,
        "constraints": {
            "max_price": 3500.0,
            "currency": "INR"
        }
    }

    res = client.post("/api/v1/ai/purchase-intents", json=payload)
    assert res.status_code == 400
    assert "exceeds buyer budget constraint" in res.json()["detail"]

def test_purchase_intent_empty_cart_rejected(client: TestClient, setup_test_data):
    m1_id = setup_test_data["m1"]
    payload = {
        "session_id": "sess_empty",
        "buyer_id": "buyer_empty",
        "merchant_id": m1_id
    }
    res = client.post("/api/v1/ai/purchase-intents", json=payload)
    assert res.status_code == 400
    assert "Cart is empty" in res.json()["detail"]

def test_purchase_intent_insufficient_inventory(client: TestClient, db: Session, setup_test_data):
    m1_id = setup_test_data["m1"]
    session_id = "sess_no_stock"

    p1 = Product(merchant_id=m1_id, name="Pro Running Shoes", price=Decimal("3499.00"), category="Running", is_active=True)
    db.add(p1)
    db.flush()
    inv = Inventory(merchant_id=m1_id, product_id=p1.id, stock_quantity=1)
    db.add(inv)
    db.commit()

    add_to_cart(db=db, merchant_id=m1_id, session_id=session_id, product_id=p1.id, quantity=1)

    # Reduce inventory to 0 before intent creation
    inv.stock_quantity = 0
    db.commit()

    payload = {
        "session_id": session_id,
        "buyer_id": "buyer_test",
        "merchant_id": m1_id
    }
    res = client.post("/api/v1/ai/purchase-intents", json=payload)
    assert res.status_code == 400
    assert "Insufficient inventory" in res.json()["detail"]

def test_purchase_intent_expiration(client: TestClient, db: Session, setup_test_data):
    m1_id = setup_test_data["m1"]
    session_id = "sess_exp_001"

    p1 = Product(merchant_id=m1_id, name="Pro Running Shoes", price=Decimal("3499.00"), category="Running", is_active=True)
    db.add(p1)
    db.flush()
    db.add(Inventory(merchant_id=m1_id, product_id=p1.id, stock_quantity=10))
    db.commit()

    add_to_cart(db=db, merchant_id=m1_id, session_id=session_id, product_id=p1.id, quantity=1)

    res = client.post("/api/v1/ai/purchase-intents", json={
        "session_id": session_id,
        "buyer_id": "buyer_exp",
        "merchant_id": m1_id
    })
    intent_id = res.json()["id"]

    # Manually simulate time expiration in DB
    intent = db.query(PurchaseIntent).filter(PurchaseIntent.id == intent_id).first()
    past_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=20)
    intent.expires_at = past_time
    db.commit()

    # Retrieve purchase intent
    res_get = client.get(f"/api/v1/purchase-intents/{intent_id}")
    assert res_get.status_code == 200
    assert res_get.json()["status"] == "EXPIRED"

def test_list_purchase_intents(client: TestClient, db: Session, setup_test_data):
    m1_id = setup_test_data["m1"]
    session_id = "sess_list_001"

    p1 = Product(merchant_id=m1_id, name="Pro Running Shoes", price=Decimal("3499.00"), category="Running", is_active=True)
    db.add(p1)
    db.flush()
    db.add(Inventory(merchant_id=m1_id, product_id=p1.id, stock_quantity=10))
    db.commit()

    add_to_cart(db=db, merchant_id=m1_id, session_id=session_id, product_id=p1.id, quantity=1)

    client.post("/api/v1/ai/purchase-intents", json={
        "session_id": session_id,
        "buyer_id": "buyer_list",
        "merchant_id": m1_id
    })

    res = client.get(f"/api/v1/purchase-intents/?merchant_id={m1_id}")
    assert res.status_code == 200
    intents = res.json()
    assert len(intents) >= 1
    assert Decimal(str(intents[0]["requested_amount"])) == Decimal("3499.00")

def test_purchase_intent_with_valid_delivery_address(client: TestClient, db: Session, setup_test_data):
    m1_id = setup_test_data["m1"]
    session_id = "sess_address_valid"

    p1 = Product(merchant_id=m1_id, name="Running Shoes", price=Decimal("2999.00"), category="Running", is_active=True)
    db.add(p1)
    db.flush()
    db.add(Inventory(merchant_id=m1_id, product_id=p1.id, stock_quantity=10))
    db.commit()

    add_to_cart(db=db, merchant_id=m1_id, session_id=session_id, product_id=p1.id, quantity=1)

    payload = {
        "session_id": session_id,
        "buyer_id": "buyer_addr_01",
        "merchant_id": m1_id,
        "delivery_address": {
            "full_name": "Kritika Bansal",
            "phone": "9876543210",
            "email": "kritika@example.com",
            "address_line1": "Flat 402, Lotus Heights, MG Road",
            "address_line2": "Indiranagar",
            "landmark": "Near Metro Station",
            "city": "Bengaluru",
            "state": "Karnataka",
            "pin_code": "560001",
            "country": "India"
        }
    }

    res = client.post("/api/v1/purchase-intents/", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["delivery_address"]["full_name"] == "Kritika Bansal"
    assert data["delivery_address"]["phone"] == "9876543210"
    assert data["delivery_address"]["city"] == "Bengaluru"
    assert data["delivery_address"]["pin_code"] == "560001"

    # Verify immutable persistence in database
    pi_db = db.query(PurchaseIntent).filter(PurchaseIntent.id == data["id"]).first()
    assert pi_db.delivery_address["full_name"] == "Kritika Bansal"
    assert pi_db.delivery_address["pin_code"] == "560001"

def test_purchase_intent_invalid_phone_rejected(client: TestClient, db: Session, setup_test_data):
    m1_id = setup_test_data["m1"]
    session_id = "sess_phone_invalid"

    p1 = Product(merchant_id=m1_id, name="Running Shoes", price=Decimal("2999.00"), category="Running", is_active=True)
    db.add(p1)
    db.flush()
    db.add(Inventory(merchant_id=m1_id, product_id=p1.id, stock_quantity=10))
    db.commit()

    add_to_cart(db=db, merchant_id=m1_id, session_id=session_id, product_id=p1.id, quantity=1)

    payload = {
        "session_id": session_id,
        "buyer_id": "buyer_phone_fail",
        "merchant_id": m1_id,
        "delivery_address": {
            "full_name": "Kritika Bansal",
            "phone": "9876543", # Only 7 digits -> Must fail
            "email": "kritika@example.com",
            "address_line1": "Flat 402, Lotus Heights",
            "city": "Bengaluru",
            "state": "Karnataka",
            "pin_code": "560001"
        }
    }

    res = client.post("/api/v1/purchase-intents/", json=payload)
    assert res.status_code == 400
    assert "Mobile number must be 10 digits" in res.json()["detail"]

def test_purchase_intent_invalid_pin_code_rejected(client: TestClient, db: Session, setup_test_data):
    m1_id = setup_test_data["m1"]
    session_id = "sess_pin_invalid"

    p1 = Product(merchant_id=m1_id, name="Running Shoes", price=Decimal("2999.00"), category="Running", is_active=True)
    db.add(p1)
    db.flush()
    db.add(Inventory(merchant_id=m1_id, product_id=p1.id, stock_quantity=10))
    db.commit()

    add_to_cart(db=db, merchant_id=m1_id, session_id=session_id, product_id=p1.id, quantity=1)

    payload = {
        "session_id": session_id,
        "buyer_id": "buyer_pin_fail",
        "merchant_id": m1_id,
        "delivery_address": {
            "full_name": "Kritika Bansal",
            "phone": "9876543210",
            "email": "kritika@example.com",
            "address_line1": "Flat 402, Lotus Heights",
            "city": "Bengaluru",
            "state": "Karnataka",
            "pin_code": "5600" # Only 4 digits -> Must fail
        }
    }

    res = client.post("/api/v1/purchase-intents/", json=payload)
    assert res.status_code == 400
    assert "PIN code must be 6 digits" in res.json()["detail"]

