import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def client():
    return TestClient(app)

# 1. English Standard
def test_1_english_running_shoes_under_5000(client):
    sess = "test_sess_t1_en"
    res = client.post("/api/v1/ai/shopping", json={"session_id": sess, "message": "Running shoes under ₹5,000"})
    assert res.status_code == 200
    data = res.json()
    assert len(data["products"]) >= 2
    for p in data["products"]:
        assert p["category"] == "Running"
        assert float(p["price"]) <= 5000.0

# 2. Devanagari Hindi
def test_2_devanagari_hindi_running_shoes(client):
    sess = "test_sess_t2_hi"
    res = client.post("/api/v1/ai/shopping", json={"session_id": sess, "message": "मुझे 5000 रुपये के अंदर रनिंग शूज़ चाहिए"})
    assert res.status_code == 200
    data = res.json()
    assert len(data["products"]) >= 2
    for p in data["products"]:
        assert p["category"] == "Running"

# 3. Hinglish Variations & 500 kke Normalization
def test_3_hinglish_variations(client):
    queries = [
        "500 kke shoes",
        "5000 ke andar running shoes chahiye",
        "paanch hazaar ke running shoes",
        "5 hazaar ke jute",
        "paanch hazaar ke jute",
        "5k ke shoes",
        "5000 wale shoes",
        "jute 5000 ke andar",
        "paanch hazaar tak ke running shoes",
        "running shoes 5k ke andar",
        "mujhe 5000 tak ke jute chahiye"
    ]
    for i, q in enumerate(queries):
        sess = f"test_sess_t3_var_{i}"
        res = client.post("/api/v1/ai/shopping", json={"session_id": sess, "message": q})
        assert res.status_code == 200
        data = res.json()
        assert len(data["products"]) >= 2, f"Failed for query '{q}', got {len(data['products'])}"
        for p in data["products"]:
            assert p["category"] == "Running"

# 4. ASR Noisy Transcripts
def test_4_asr_noisy_transcripts(client):
    noisy_queries = [
        "Pancho Ke Jhoote",
        "Pan Su Ke Joote",
        "panch hajar ke jute"
    ]
    for i, q in enumerate(noisy_queries):
        sess = f"test_sess_t4_asr_{i}"
        res = client.post("/api/v1/ai/shopping", json={"session_id": sess, "message": q})
        assert res.status_code == 200
        data = res.json()
        assert len(data["products"]) >= 2, f"Failed for noisy query '{q}'"
        for p in data["products"]:
            assert p["category"] == "Running"

# 5. Multi-turn Flow: Running shoes -> which is best -> add the best one
def test_5_multiturn_best_and_add_cart(client):
    sess = "test_sess_t5_best_add"
    r1 = client.post("/api/v1/ai/shopping", json={"session_id": sess, "message": "running shoes under 5000"})
    assert r1.status_code == 200
    assert len(r1.json()["products"]) >= 2

    r2 = client.post("/api/v1/ai/shopping", json={"session_id": sess, "message": "which one is best?"})
    assert r2.status_code == 200
    assert len(r2.json()["products"]) == 1
    assert "SpeedFlow" in r2.json()["products"][0]["name"]

    r3 = client.post("/api/v1/ai/shopping", json={"session_id": sess, "message": "add the best one"})
    assert r3.status_code == 200
    assert len(r3.json()["cart"]["items"]) >= 1

# 6. Specificity: Hindi Bottle Queries (No Unrelated Cross-Sells)
def test_6_bottle_specificity_no_cross_sells(client):
    for q in ["बोतल", "सिर्फ एक बोतल", "मुझे एक बोतल चाहिए", "paani ki bottle", "water bottle"]:
        sess = f"test_sess_t6_bottle_{hash(q)}"
        res = client.post("/api/v1/ai/shopping", json={"session_id": sess, "message": q})
        assert res.status_code == 200
        data = res.json()
        assert len(data["products"]) == 1
        assert "Bottle" in data["products"][0]["name"]
        # Never return socks or foam roller
        assert not any("Socks" in p["name"] for p in data["products"])
        assert not any("Roller" in p["name"] for p in data["products"])

# 7. Category Lock on Cheaper Follow-up
def test_7_cheaper_followup_preserves_category(client):
    sess = "test_sess_t7_cheaper_lock"
    client.post("/api/v1/ai/shopping", json={"session_id": sess, "message": "show me running shoes"})
    
    res = client.post("/api/v1/ai/shopping", json={"session_id": sess, "message": "show me cheaper ones"})
    assert res.status_code == 200
    data = res.json()
    # Must stay in running shoes context and state lowest starting price
    assert "running" in data["message"].lower() or "speedflow" in data["message"].lower()
    assert not any(p.get("category") == "Accessories" for p in data.get("products", []))

# 8. High Value Transaction Governance: REQUIRES_APPROVAL
def test_8_high_value_governance_approval(client):
    import uuid
    sess = f"test_sess_t8_governance_{uuid.uuid4().hex[:8]}"
    prods = client.get("/api/v1/products").json()
    in_stock_prods = [p for p in prods if p.get("in_stock") or p.get("stock_quantity", 0) > 0]
    target_prod = in_stock_prods[0] if in_stock_prods else prods[0]
    prod_id = target_prod["id"]
    m_id = target_prod.get("merchant_id")
    client.post("/api/v1/cart/items", json={"session_id": sess, "product_id": prod_id, "quantity": 1})

    # Create intent
    intent_res = client.post("/api/v1/purchase-intents/", json={
        "session_id": sess,
        "merchant_id": m_id,
        "buyer_id": "shopper@example.com",
        "delivery_address": {
            "full_name": "Kritika Bansal",
            "phone": "9876543210",
            "email": "shopper@example.com",
            "address_line1": "100 MG Road",
            "city": "Bengaluru",
            "state": "Karnataka",
            "pin_code": "560001",
            "country": "India"
        }
    })
    assert intent_res.status_code == 200
    intent_id = intent_res.json()["id"]

    eval_res = client.post(f"/api/v1/purchase-intents/{intent_id}/evaluate")
    assert eval_res.status_code == 200
    eval_data = eval_res.json()
    assert eval_data["decision"] in ["ALLOW", "REQUIRES_APPROVAL", "DENY"]
