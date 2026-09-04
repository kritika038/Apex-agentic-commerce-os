import pytest
import io
import uuid
from decimal import Decimal
from fastapi.testclient import TestClient

from app.main import app
from app.database.session import SessionLocal
from app.database.models.merchant import Merchant
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.user import User
from app.database.models.purchase_intent import PurchaseIntent
from app.database.models.policy_evaluation import PolicyEvaluation
from app.database.models.transaction_authorization import TransactionAuthorization
from app.database.models.payment_transaction import PaymentTransaction
from datetime import datetime, timezone, timedelta

client = TestClient(app)

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        merchant = db.query(Merchant).filter(Merchant.is_active == True).first()
        yield db, merchant
    finally:
        db.close()


def test_1_multimodal_conversational_search_hindi_hinglish_budget(db_session):
    db, m = db_session
    m_id = m.id if m else None
    
    # 1. English with budget
    res1 = client.post("/api/v1/search/conversational", json={"query": "Running shoes under ₹5,000", "merchant_id": m_id})
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["intent"]["budget_max"] == 5000
    assert data1["intent"]["category"] == "Footwear"
    assert data1["total_results"] >= 1

    # 2. Hinglish with Devanagari/Hinglish token
    res2 = client.post("/api/v1/search/conversational", json={"query": "Bhai 3000 ke andar marathon shoes dikhaye", "merchant_id": m_id})
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["intent"]["budget_max"] == 3000
    assert data2["intent"]["language"] in ["hinglish", "hindi"]

    # 3. Catalog dynamic filters
    res3 = client.get(f"/api/v1/search/filters" + (f"?merchant_id={m_id}" if m_id else ""))
    assert res3.status_code == 200
    filters = res3.json()
    assert "categories" in filters
    assert len(filters["categories"]) >= 1
    assert "price_bounds" in filters


def test_2_visual_search_image_feature_extraction(db_session):
    db, m = db_session
    m_id = m.id if m else None
    
    # Create a synthetic test image byte stream
    img_bytes = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\x00\x00\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
    
    files = {"file": ("test_shoe.gif", img_bytes, "image/gif")}
    data = {"merchant_id": m_id} if m_id else {}
    res = client.post("/api/v1/search/visual", files=files, data=data)
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["total_found"] >= 1
    assert "results" in res_data
    top_match = res_data["results"][0]
    assert "similarity_score" in top_match
    assert top_match["similarity_score"] > 0.3
    assert top_match["in_stock"] is True


def test_3_personalization_interaction_signals_and_cold_start(db_session):
    db, m = db_session
    m_id = m.id if m else None
    prod = db.query(Product).filter(Product.is_active == True).first()
    assert prod is not None

    # 1. Cold start request (no session/user history)
    res1 = client.get(f"/api/v1/personalization/home" + (f"?merchant_id={m_id}" if m_id else ""))
    assert res1.status_code == 200
    data1 = res1.json()
    assert "recommended_for_you" in data1
    assert len(data1["recommended_for_you"]["products"]) >= 1

    # 2. Record interaction for a session
    sess_id = f"test_sess_pers_{uuid.uuid4().hex[:6]}"
    rec_res = client.post("/api/v1/personalization/interactions", json={
        "product_id": prod.id,
        "event_type": "PRODUCT_VIEW",
        "session_id": sess_id,
        "metadata": {"source": "storefront"}
    }, params={"merchant_id": m_id} if m_id else {})
    assert rec_res.status_code == 200

    # 3. Personalized feed for returning session
    res2 = client.get(f"/api/v1/personalization/home?session_id={sess_id}" + (f"&merchant_id={m_id}" if m_id else ""))
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["is_cold_start"] is False
    assert data2["continue_shopping"] is not None
    assert data2["continue_shopping"]["products"][0]["id"] == prod.id


def test_4_product_bundles_and_affinity(db_session):
    db, m = db_session
    m_id = m.id if m else None
    prod = db.query(Product).filter(Product.is_active == True).first()
    assert prod is not None
    
    res = client.get(f"/api/v1/personalization/products/{prod.id}/bundles" + (f"?merchant_id={m_id}" if m_id else ""))
    assert res.status_code == 200
    bundles = res.json()
    assert isinstance(bundles, list)
    assert len(bundles) >= 1
    assert "evidence" in bundles[0]
    assert "confidence" in bundles[0]


def test_5_fit_and_review_intelligence(db_session):
    db, m = db_session
    prod = db.query(Product).filter(Product.is_active == True).first()
    assert prod is not None

    # 1. Fit recommendation
    fit_res = client.get(f"/api/v1/personalization/products/{prod.id}/fit-recommendation")
    assert fit_res.status_code == 200
    fit_data = fit_res.json()
    assert fit_data["status"] in ["RECOMMENDED", "INSUFFICIENT_DATA"]
    assert "explanation" in fit_data

    # 2. Review summary
    rev_res = client.get(f"/api/v1/personalization/products/{prod.id}/reviews/summary")
    assert rev_res.status_code == 200
    rev_data = rev_res.json()
    assert rev_data["status"] in ["AVAILABLE", "NO_REVIEWS"]
    if rev_data["status"] == "AVAILABLE":
        assert len(rev_data["pros"]) >= 1
        assert "overall_sentiment" in rev_data


def test_6_customer_support_orders_and_returns(db_session):
    db, m = db_session
    
    # 1. Support conversational chat for order tracking
    chat_res = client.post("/api/v1/customer/support/chat", json={"message": "Where is my latest order?"})
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert chat_data["intent"] == "ORDER_STATUS"

    # 2. Support rewards balance inquiry
    coin_res = client.post("/api/v1/customer/support/chat", json={"message": "How many Apex Coins do I have?"})
    assert coin_res.status_code == 200
    coin_data = coin_res.json()
    assert coin_data["intent"] == "REWARD_BALANCE"
    assert "coin_balance" in coin_data["data"]

    # 3. Return policy inquiry
    ret_res = client.post("/api/v1/customer/support/chat", json={"message": "What is the return policy?"})
    assert ret_res.status_code == 200
    assert ret_res.json()["intent"] == "RETURN_POLICY"


def test_7_merchant_inventory_health_and_customer_segments(db_session):
    db, m = db_session
    m_id = m.id if m else None
    
    # 1. Inventory health
    inv_res = client.get(f"/api/v1/revenue/inventory/health" + (f"?merchant_id={m_id}" if m_id else ""))
    assert inv_res.status_code == 200
    inv_data = inv_res.json()
    assert "healthy_stock_count" in inv_data
    assert "risk_items" in inv_data

    # 2. Customer segments
    seg_res = client.get(f"/api/v1/revenue/customers/segments" + (f"?merchant_id={m_id}" if m_id else ""))
    assert seg_res.status_code == 200
    seg_data = seg_res.json()
    assert "segments" in seg_data
    assert len(seg_data["segments"]) >= 4


def test_8_dynamic_pricing_and_transaction_risk_scoring(db_session):
    db, m = db_session
    m_id = m.id if m else None
    
    # 1. Pricing recommendations
    price_res = client.get(f"/api/v1/revenue/pricing/recommendations" + (f"?merchant_id={m_id}" if m_id else ""))
    assert price_res.status_code == 200
    price_data = price_res.json()
    assert isinstance(price_data, list)

    # 2. Advisory risk scoring
    risk_res = client.get(f"/api/v1/revenue/risk/assess?amount=4500.00" + (f"&merchant_id={m_id}" if m_id else ""))
    assert risk_res.status_code == 200
    risk_data = risk_res.json()
    assert risk_data["risk_level"] in ["LOW", "MEDIUM", "HIGH"]
    assert risk_data["is_advisory"] is True
    assert len(risk_data["reasons"]) >= 1
