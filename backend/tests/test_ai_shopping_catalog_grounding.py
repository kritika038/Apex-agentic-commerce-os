import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database.session import get_db
from app.database.models.merchant import Merchant
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.user import User
from app.agents.shopping_agent import ShoppingAgent
from app.agents.intent_engine import ConversationIntentEngine

@pytest.fixture
def setup_catalog(db: Session):
    # Ensure merchant exists
    merchant = db.query(Merchant).first()
    if not merchant:
        merchant = Merchant(
            id="m_grounding_test",
            name="Apex Official Store",
            domain="store.apex.local"
        )
        db.add(merchant)
        db.commit()
        db.refresh(merchant)

    # Clean existing test products
    db.query(Product).filter(Product.merchant_id == merchant.id).delete()
    db.commit()

    # Product 1: Air Cushion Trail Running Shoes
    p1 = Product(
        id="44d18ce3-091a-4cea-a0b5-5f6a36d28aec",
        merchant_id=merchant.id,
        name="Air Cushion Trail Running Shoes",
        brand="Apex",
        category="Footwear",
        subcategory="Running Shoes",
        price=Decimal("4299.00"),
        mrp=Decimal("4999.00"),
        description="Premium trail running shoe engineered with high-rebound Air Cushion midsole and rugged lugged traction.",
        attributes={
            "sizes": ["UK 7", "UK 8", "UK 9", "UK 10", "UK 11"],
            "colors": ["Slate Grey", "Midnight Black"],
            "size_and_fit": "True to size (Standard width)",
            "use_case": "Trail running, marathon training, and rugged terrain"
        },
        is_active=True
    )
    db.add(p1)
    db.flush()

    inv1 = Inventory(
        product_id=p1.id,
        merchant_id=merchant.id,
        stock_quantity=15,
        reserved_quantity=0
    )
    db.add(inv1)

    # Product 2: SpeedFlow Marathon Shoes
    p2 = Product(
        id="prod_speedflow_001",
        merchant_id=merchant.id,
        name="SpeedFlow Marathon Shoes",
        brand="Apex",
        category="Footwear",
        subcategory="Running Shoes",
        price=Decimal("2999.00"),
        mrp=Decimal("3499.00"),
        description="Ultralight marathon racing shoes with carbon plate energy return.",
        attributes={
            "sizes": ["UK 8", "UK 9", "UK 10"],
            "colors": ["Neon Green", "Volt Yellow"],
        },
        is_active=True
    )
    db.add(p2)
    db.flush()

    inv2 = Inventory(
        product_id=p2.id,
        merchant_id=merchant.id,
        stock_quantity=8,
        reserved_quantity=0
    )
    db.add(inv2)

    # Product 3: Insulated Water Bottle
    p3 = Product(
        id="prod_bottle_001",
        merchant_id=merchant.id,
        name="Insulated Stainless Steel Water Bottle",
        brand="Apex",
        category="Accessories",
        subcategory="Bottles",
        price=Decimal("799.00"),
        mrp=Decimal("999.00"),
        description="750ml vacuum insulated stainless steel water bottle.",
        is_active=True
    )
    db.add(p3)
    db.flush()

    inv3 = Inventory(
        product_id=p3.id,
        merchant_id=merchant.id,
        stock_quantity=25,
        reserved_quantity=0
    )
    db.add(inv3)

    db.commit()
    return merchant, p1, p2, p3


def test_intent_engine_detects_product_inquiry():
    msg = "Tell me more about Air Cushion Trail Running Shoes and why it is good for Running."
    res = ConversationIntentEngine.analyze_message(message=msg)
    assert res["action"] == "PRODUCT_INQUIRY"
    assert res["inquiry_type"] in ["WHY_GOOD_FOR_USE_CASE", "GENERAL"]
    assert res["product_name_query"] == "Air Cushion Trail Running Shoes"


def test_intent_engine_deictic_with_current_product():
    curr = {"id": "44d18ce3-091a-4cea-a0b5-5f6a36d28aec", "name": "Air Cushion Trail Running Shoes"}
    msg = "Why is it good for running?"
    res = ConversationIntentEngine.analyze_message(message=msg, current_product=curr)
    assert res["action"] == "PRODUCT_INQUIRY"
    assert res["inquiry_type"] == "WHY_GOOD_FOR_USE_CASE"
    assert res["product_id"] == "44d18ce3-091a-4cea-a0b5-5f6a36d28aec"


def test_shopping_agent_grounded_response_by_product_name(db: Session, setup_catalog):
    merchant, p1, p2, p3 = setup_catalog
    agent = ShoppingAgent(
        db=db,
        merchant_id=merchant.id,
        session_id="sess_test_grounding_01"
    )
    res = agent.process_message("Tell me more about Air Cushion Trail Running Shoes and why it is good for Running.")
    assert "Air Cushion Trail Running Shoes" in res.message
    assert "4,299" in res.message
    assert "UK 7" in res.message
    assert len(res.products) == 1
    assert res.products[0]["id"] == p1.id
    assert res.products[0]["price"] == 4299.0


def test_shopping_agent_grounded_response_with_product_id_context(db: Session, setup_catalog):
    merchant, p1, p2, p3 = setup_catalog
    agent = ShoppingAgent(
        db=db,
        merchant_id=merchant.id,
        session_id="sess_test_grounding_02",
        product_id=p1.id
    )
    res = agent.process_message("Why is this good for running?")
    assert "Air Cushion Trail Running Shoes" in res.message
    assert "Cushioning" in res.message
    assert "4,299" in res.message
    assert len(res.products) == 1
    assert res.products[0]["id"] == p1.id


def test_shopping_agent_price_inquiry(db: Session, setup_catalog):
    merchant, p1, p2, p3 = setup_catalog
    agent = ShoppingAgent(
        db=db,
        merchant_id=merchant.id,
        session_id="sess_test_grounding_03",
        product_id=p1.id
    )
    res = agent.process_message("What is the price?")
    assert "4,299" in res.message
    assert "Air Cushion Trail Running Shoes" in res.message


def test_shopping_agent_stock_inquiry(db: Session, setup_catalog):
    merchant, p1, p2, p3 = setup_catalog
    agent = ShoppingAgent(
        db=db,
        merchant_id=merchant.id,
        session_id="sess_test_grounding_04",
        product_id=p1.id
    )
    res = agent.process_message("Is it in stock?")
    assert "in stock" in res.message.lower() or "stock mein available" in res.message.lower()
    assert "15" in res.message


def test_shopping_agent_sizes_inquiry(db: Session, setup_catalog):
    merchant, p1, p2, p3 = setup_catalog
    agent = ShoppingAgent(
        db=db,
        merchant_id=merchant.id,
        session_id="sess_test_grounding_05",
        product_id=p1.id
    )
    res = agent.process_message("What sizes are available?")
    assert "UK 7" in res.message
    assert "UK 11" in res.message


def test_shopping_agent_trail_vs_road(db: Session, setup_catalog):
    merchant, p1, p2, p3 = setup_catalog
    agent = ShoppingAgent(
        db=db,
        merchant_id=merchant.id,
        session_id="sess_test_grounding_06",
        product_id=p1.id
    )
    res = agent.process_message("Is this better for trail running or road running?")
    assert "Trail Running" in res.message


def test_shopping_agent_hinglish_inquiry(db: Session, setup_catalog):
    merchant, p1, p2, p3 = setup_catalog
    agent = ShoppingAgent(
        db=db,
        merchant_id=merchant.id,
        session_id="sess_test_grounding_07",
        product_id=p1.id
    )
    res = agent.process_message("Ye shoe running ke liye kaisa hai aur iska price kitna hai?")
    assert "Air Cushion Trail Running Shoes" in res.message
    assert "4,299" in res.message


def test_shopping_agent_unknown_product_zero_hallucination(db: Session, setup_catalog):
    merchant, p1, p2, p3 = setup_catalog
    agent = ShoppingAgent(
        db=db,
        merchant_id=merchant.id,
        session_id="sess_test_grounding_08"
    )
    res = agent.process_message("Tell me about SuperSonic Flying Hoverboard 3000")
    assert "couldn't find" in res.message.lower() or "nahi mila" in res.message.lower()
    assert len(res.products) == 0


def test_multi_turn_flow_with_purchase(db: Session, setup_catalog):
    merchant, p1, p2, p3 = setup_catalog
    session_id = "sess_test_grounding_multiturn"
    agent = ShoppingAgent(
        db=db,
        merchant_id=merchant.id,
        session_id=session_id,
        product_id=p1.id
    )
    # Turn 1: Product inquiry on PDP
    r1 = agent.process_message("Tell me more about this product")
    assert "Air Cushion Trail Running Shoes" in r1.message

    # Turn 2: Follow up question without mentioning product name
    r2 = agent.process_message("What is the price?")
    assert "4,299" in r2.message

    # Turn 3: Purchase command
    r3 = agent.process_message("Order this one")
    assert r3.order_review is not None
    assert len(r3.order_review.items) == 1
    assert r3.order_review.items[0].product_id == p1.id
    assert r3.order_review.items[0].price == 4299.0


def test_api_shopping_and_chat_endpoints(client, db: Session, setup_catalog):
    merchant, p1, p2, p3 = setup_catalog

    # 1. Test /api/v1/ai/shopping
    res_shopping = client.post("/api/v1/ai/shopping", json={
        "session_id": "sess_api_01",
        "merchant_id": merchant.id,
        "message": "Tell me more about Air Cushion Trail Running Shoes",
        "product_id": p1.id
    })
    assert res_shopping.status_code == 200
    data1 = res_shopping.json()
    assert "Air Cushion Trail Running Shoes" in data1["message"]
    assert data1["reply"] == data1["message"]

    # 2. Test /api/v1/ai/chat alias
    res_chat = client.post("/api/v1/ai/chat", json={
        "session_id": "sess_api_02",
        "merchant_id": merchant.id,
        "message": "Tell me more about Air Cushion Trail Running Shoes and why it is good for Running.",
        "product_id": p1.id
    })
    assert res_chat.status_code == 200
    data2 = res_chat.json()
    assert "Air Cushion Trail Running Shoes" in data2["message"]
    assert "4,299" in data2["message"]
    assert data2["reply"] == data2["message"]
    assert len(data2["products"]) == 1
    assert data2["products"][0]["id"] == p1.id
