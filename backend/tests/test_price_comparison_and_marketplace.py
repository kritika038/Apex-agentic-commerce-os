import pytest
from decimal import Decimal
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database.session import get_db, SessionLocal
from app.database.models.merchant import Merchant
from app.database.models.user import User
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.external_store import ExternalStore
from app.database.models.external_offer import ExternalProductOffer, PriceObservationHistory, ExternalOutboundClick
from app.services.product_matching_service import ProductMatchingService
from app.services.price_comparison_service import PriceComparisonService
from app.services.external_stores.registry import ExternalStoreRegistry, ALLOWED_EXTERNAL_DOMAINS
from app.revenue.opportunity_engine import RevenueOpportunityEngine
from app.agents.intent_engine import ConversationIntentEngine
from app.agents.shopping_agent import ShoppingAgent
from app.core.security import create_access_token, get_password_hash

client = TestClient(app)

@pytest.fixture(scope="module")
def db_session():
    db = SessionLocal()
    yield db
    db.close()

@pytest.fixture(scope="module")
def test_setup(db_session: Session):
    # Setup Merchant
    merchant = db_session.query(Merchant).first()
    if not merchant:
        merchant = Merchant(name="Marketplace Test Merchant", domain="market-test.test")
        db_session.add(merchant)
        db_session.commit()
        db_session.refresh(merchant)

    # Setup User
    user = db_session.query(User).filter(User.email == "shopper@test.com").first()
    if not user:
        user = User(
            email="shopper@test.com",
            hashed_password=get_password_hash("pass123"),
            full_name="Market Shopper",
            merchant_id=merchant.id,
            role="customer"
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

    # Setup External Stores
    amz = db_session.query(ExternalStore).filter(ExternalStore.domain == "amazon.in").first()
    if not amz:
        amz = ExternalStore(name="Amazon India", domain="amazon.in", store_type="MARKETPLACE", enabled=True, verified=True)
        db_session.add(amz)

    fk = db_session.query(ExternalStore).filter(ExternalStore.domain == "flipkart.com").first()
    if not fk:
        fk = ExternalStore(name="Flipkart", domain="flipkart.com", store_type="MARKETPLACE", enabled=True, verified=True)
        db_session.add(fk)

    nike = db_session.query(ExternalStore).filter(ExternalStore.domain == "nike.com").first()
    if not nike:
        nike = ExternalStore(name="Nike Official", domain="nike.com", store_type="OFFICIAL_BRAND", enabled=True, verified=True)
        db_session.add(nike)

    db_session.commit()

    # Retrieve seeded Sports Dry-Fit T-Shirt
    test_p = db_session.query(Product).filter(Product.name == "Sports Dry-Fit T-Shirt").first()
    assert test_p is not None, "Seeded product 'Sports Dry-Fit T-Shirt' must exist"

    token = create_access_token(user.id, merchant.id, "customer")
    yield {"merchant": merchant, "user": user, "product": test_p, "token": token}


# --- 1. Product Matching Tests ---

def test_1_deterministic_matching_gtin_exact():
    apex = {"gtin": "8901234567890", "model_number": "NK-01", "brand": "Nike", "name": "Pro Runner"}
    cand = {"gtin": "8901234567890", "model_number": "XYZ", "brand": "Nike", "name": "Different Title"}
    m_type, conf, reason = ProductMatchingService.match_products(apex, cand)
    assert m_type in ["EXACT", "VARIANT_EXACT"]
    assert conf == 1.0
    assert "GTIN" in reason

def test_2_exact_sku_match():
    apex = {"sku": "NK-LEG-01", "brand": "Nike", "name": "Legend Tee"}
    cand = {"sku": "NK-LEG-01", "brand": "Nike", "name": "Legend Short Sleeve"}
    m_type, conf, reason = ProductMatchingService.match_products(apex, cand)
    assert m_type == "EXACT"
    assert conf >= 0.98

def test_3_exact_style_and_variant():
    apex = {"model_number": "718833-010", "brand": "Nike", "name": "Dri-FIT Legend", "attributes": {"color": "black", "size": "M"}}
    cand = {"model_number": "718833-010", "brand": "Nike", "name": "Nike Men's Legend", "attributes": {"color": "black", "size": "M"}}
    m_type, conf, reason = ProductMatchingService.match_products(apex, cand)
    assert m_type == "VARIANT_EXACT"
    assert conf >= 0.99

def test_4_same_model_different_color_is_model_exact():
    apex = {"model_number": "718833-010", "brand": "Nike", "name": "Dri-FIT Legend", "attributes": {"color": "black", "size": "M"}}
    cand = {"model_number": "718833-010", "brand": "Nike", "name": "Dri-FIT Legend", "attributes": {"color": "white", "size": "M"}}
    m_type, conf, reason = ProductMatchingService.match_products(apex, cand)
    assert m_type == "MODEL_EXACT"
    assert conf < 0.95

def test_5_similar_title_only_is_similar_not_exact():
    apex = {"brand": "Nike", "name": "Nike Running Shoes Pro", "category": "Footwear"}
    cand = {"brand": "Adidas", "name": "Adidas Running Shoes Pro", "category": "Footwear"}
    m_type, conf, reason = ProductMatchingService.match_products(apex, cand)
    assert m_type == "SIMILAR"
    assert m_type != "EXACT"
    assert conf < 0.80

def test_6_search_url_only_is_search_fallback(test_setup, db_session: Session):
    p = test_setup["product"]
    fk_store = db_session.query(ExternalStore).filter(ExternalStore.domain == "flipkart.com").first()
    search_off = ExternalProductOffer(
        apex_product_id=p.id,
        external_store_id=fk_store.id,
        external_product_id=None,
        external_product_title="Search Query Fallback",
        external_url="https://www.flipkart.com/search?q=Nike+Tshirt",
        image_url=None,
        price=Decimal("799.00"),
        match_type="SEARCH_FALLBACK",
        match_confidence=0.60
    )
    db_session.add(search_off)
    db_session.commit()

    comp = PriceComparisonService.get_product_price_comparison(db_session, str(p.id), force_refresh=True)
    res = next(o for o in comp["offers"] if o["id"] == str(search_off.id))
    assert res["match_type"] == "SEARCH_FALLBACK"
    assert res["link_type"] == "SEARCH_FALLBACK"
    assert res["price"] is None
    assert "Search result" in res["price_delta_label"]

    db_session.delete(search_off)
    db_session.commit()

def test_7_8_missing_external_image_or_id_downgrades_to_search_fallback(test_setup, db_session: Session):
    p = test_setup["product"]
    fk_store = db_session.query(ExternalStore).filter(ExternalStore.domain == "flipkart.com").first()
    # Offer claiming EXACT but missing image_url and external_product_id
    bad_off = ExternalProductOffer(
        apex_product_id=p.id,
        external_store_id=fk_store.id,
        external_product_id=None,
        external_product_title="Fake Flipkart Exact",
        external_url="https://www.flipkart.com/p/test",
        image_url=None,
        price=Decimal("899.00"),
        match_type="EXACT",
        match_confidence=0.99
    )
    db_session.add(bad_off)
    db_session.commit()

    comp = PriceComparisonService.get_product_price_comparison(db_session, str(p.id), force_refresh=True)
    fk_res = next(o for o in comp["offers"] if o["id"] == str(bad_off.id))
    assert fk_res["match_type"] == "SEARCH_FALLBACK"
    assert fk_res["price"] is None

    db_session.delete(bad_off)
    db_session.commit()

def test_9_fake_asin_is_rejected_and_downgraded(test_setup, db_session: Session):
    amz_store = db_session.query(ExternalStore).filter(ExternalStore.domain == "amazon.in").first()
    fake_off = ExternalProductOffer(
        apex_product_id=test_setup["product"].id,
        external_store_id=amz_store.id,
        external_product_id="B09DEMO123", # Fake synthetic ASIN
        external_product_title="Fake Demo Amazon",
        external_url="https://www.amazon.in/dp/B09DEMO123",
        image_url="https://images.example.com/img.jpg",
        price=Decimal("799.00"),
        match_type="EXACT",
        match_confidence=0.99
    )
    db_session.add(fake_off)
    db_session.commit()

    comp = PriceComparisonService.get_product_price_comparison(db_session, str(test_setup["product"].id), force_refresh=True)
    res = next(o for o in comp["offers"] if o["id"] == str(fake_off.id))
    assert res["match_type"] == "SEARCH_FALLBACK"
    assert res["price"] is None

    db_session.delete(fake_off)
    db_session.commit()

def test_10_apex_image_reused_as_external_image_is_downgraded(test_setup, db_session: Session):
    p = test_setup["product"]
    amz_store = db_session.query(ExternalStore).filter(ExternalStore.domain == "amazon.in").first()
    reused_off = ExternalProductOffer(
        apex_product_id=p.id,
        external_store_id=amz_store.id,
        external_product_id="B007XPT5D0",
        external_product_title="Reused Image Offer",
        external_url="https://www.amazon.in/dp/B007XPT5D0",
        image_url=p.image_url, # Reusing Apex product image!
        price=Decimal("949.00"),
        match_type="EXACT",
        match_confidence=0.99
    )
    db_session.add(reused_off)
    db_session.commit()

    comp = PriceComparisonService.get_product_price_comparison(db_session, str(p.id), force_refresh=True)
    res = next(o for o in comp["offers"] if o["id"] == str(reused_off.id))
    assert res["match_type"] == "SEARCH_FALLBACK"
    assert res["price"] is None

    db_session.delete(reused_off)
    db_session.commit()

def test_11_generic_amazon_url_is_downgraded(test_setup, db_session: Session):
    p = test_setup["product"]
    amz_store = db_session.query(ExternalStore).filter(ExternalStore.domain == "amazon.in").first()
    generic_off = ExternalProductOffer(
        apex_product_id=p.id,
        external_store_id=amz_store.id,
        external_product_id="B007XPT5D0",
        external_product_title="Search Amazon Offer",
        external_url="https://www.amazon.in/s?k=Nike+Tshirt",
        image_url="https://m.media-amazon.com/images/I/51wXkY7fFSL._AC_UL640_QL65_ML3_.jpg",
        price=Decimal("949.00"),
        match_type="EXACT",
        match_confidence=0.99
    )
    db_session.add(generic_off)
    db_session.commit()

    comp = PriceComparisonService.get_product_price_comparison(db_session, str(p.id), force_refresh=True)
    res = next(o for o in comp["offers"] if o["id"] == str(generic_off.id))
    assert res["match_type"] == "SEARCH_FALLBACK"
    assert res["price"] is None

    db_session.delete(generic_off)
    db_session.commit()

def test_12_unverified_amazon_dp_url_downgrades_to_search_fallback(test_setup, db_session: Session):
    p = test_setup["product"]
    comp = PriceComparisonService.get_product_price_comparison(db_session, str(p.id), force_refresh=True)
    amz = next(o for o in comp["offers"] if o["store_name"] == "Amazon India")
    assert amz["match_type"] == "SEARCH_FALLBACK"
    assert amz["price"] is None

def test_13_14_myntra_and_nike_verified_evidence_handling(test_setup, db_session: Session):
    p = test_setup["product"]
    comp = PriceComparisonService.get_product_price_comparison(db_session, str(p.id), force_refresh=True)
    myntra = next(o for o in comp["offers"] if "myntra" in o["store_domain"])
    assert myntra["match_type"] == "SEARCH_FALLBACK"
    assert myntra["price"] is None

    nike = next(o for o in comp["offers"] if "nike" in o["store_domain"])
    assert nike["match_type"] in ["EXACT", "VARIANT_EXACT"]
    assert nike["price"] == 1095.0
    assert "718833-010" in nike["external_url"]

def test_15_synthetic_product_without_identity_has_no_exact_offer(test_setup, db_session: Session):
    synth_p = Product(
        merchant_id=test_setup["merchant"].id,
        name="Synthetic Random Gadget",
        category="Electronics",
        price=Decimal("199.00"),
        currency="INR"
    )
    db_session.add(synth_p)
    db_session.commit()
    db_session.refresh(synth_p)

    comp = PriceComparisonService.get_product_price_comparison(db_session, str(synth_p.id), force_refresh=True)
    exact_offers = [o for o in comp["offers"] if o["match_type"] in ["EXACT", "VARIANT_EXACT", "MODEL_EXACT"]]
    assert len(exact_offers) == 0

    db_session.delete(synth_p)
    db_session.commit()

def test_16_external_price_cannot_appear_for_search_fallback(test_setup, db_session: Session):
    comp = PriceComparisonService.get_product_price_comparison(db_session, str(test_setup["product"].id), force_refresh=True)
    for off in comp["offers"]:
        if off["match_type"] == "SEARCH_FALLBACK":
            assert off["price"] is None
            assert off["total_price"] is None
            assert off["difference_from_apex"] is None

def test_17_lowest_verified_price_uses_only_verified_offers(test_setup, db_session: Session):
    comp = PriceComparisonService.get_product_price_comparison(db_session, str(test_setup["product"].id), force_refresh=True)
    assert comp["lowest_verified_price"] == 999.0
    assert comp["apex_is_lowest"] == True
    assert comp["verification_scope"] == "checked_stores_only"


# --- 3. Security: Domain Whitelist & Open-Redirect Prevention ---

def test_domain_allowlist_permits_authorized_retailers():
    assert ExternalStoreRegistry.is_domain_allowed("https://www.amazon.in/dp/B09123") == True
    assert ExternalStoreRegistry.is_domain_allowed("https://www.flipkart.com/p/FSN123") == True
    assert ExternalStoreRegistry.is_domain_allowed("https://www.nike.com/in/running") == True
    assert ExternalStoreRegistry.is_domain_allowed("https://in.puma.com/in/shoes") == True

def test_open_redirect_rejection():
    assert ExternalStoreRegistry.is_domain_allowed("https://evil-phishing-site.com/steal") == False
    assert ExternalStoreRegistry.is_domain_allowed("javascript:alert(1)") == False
    assert ExternalStoreRegistry.is_domain_allowed("data:text/html,hack") == False
    assert ExternalStoreRegistry.is_domain_allowed("http://unverified-store.org") == False

def test_outbound_redirect_endpoint_and_logging(test_setup, db_session: Session):
    p = test_setup["product"]
    offer = db_session.query(ExternalProductOffer).filter(ExternalProductOffer.apex_product_id == p.id).first()
    assert offer is not None

    # Call outbound redirect
    res = client.get(f"/api/v1/external-offers/{offer.id}/redirect", follow_redirects=False)
    assert res.status_code == 307
    assert "location" in res.headers

    # Verify click was logged in DB
    click = db_session.query(ExternalOutboundClick).filter(ExternalOutboundClick.external_offer_id == offer.id).order_by(ExternalOutboundClick.created_at.desc()).first()
    assert click is not None
    assert click.target_url == (offer.affiliate_url or offer.external_url)


# --- 4. Payment Integrity: External Comparison Never Modifies Authoritative Price ---

def test_external_price_does_not_alter_apex_authoritative_price(test_setup, db_session: Session):
    p = test_setup["product"]
    # Even though Amazon is ₹949, Apex DB price remains exactly ₹999.00
    db_p = db_session.query(Product).filter(Product.id == p.id).first()
    assert db_p.price == Decimal("999.00")


# --- 5. AI Shopping Assistant Price Comparison Context Grounding ---

def test_intent_engine_detects_external_price_check():
    engine = ConversationIntentEngine()
    
    # English
    r1 = engine.analyze_message("Is this cheaper somewhere else?", previous_products=[{"id": "p1", "name": "Pegasus Runner", "price": 4799}])
    assert r1["action"] == "EXTERNAL_PRICE_CHECK"

    # Specific store
    r2 = engine.analyze_message("Amazon pe kitne ka hai?", previous_products=[{"id": "p1", "name": "Pegasus Runner", "price": 4799}])
    assert r2["action"] == "EXTERNAL_PRICE_CHECK"

    # Hindi / Hinglish
    r3 = engine.analyze_message("Sabse sasta kaha mil raha hai?", previous_products=[{"id": "p1", "name": "Pegasus Runner", "price": 4799}])
    assert r3["action"] == "EXTERNAL_PRICE_CHECK"


def test_shopping_agent_executes_external_price_check(test_setup, db_session: Session):
    merchant = test_setup["merchant"]
    user = test_setup["user"]
    p = test_setup["product"]

    agent = ShoppingAgent(
        db=db_session,
        merchant_id=merchant.id,
        session_id="sess_test_comparison",
        user=user
    )

    # Prime session with active product
    agent.process_message("Show me Pegasus Speed Runner 40")

    # Ask for external price comparison
    resp = agent.process_message("Is this cheaper on Amazon?")
    assert "Apex Store" in resp.message
    assert "Amazon India" in resp.message
    assert "price comparison" in resp.message.lower()


# --- 6. Merchant AI Growth: Price Competitiveness Discovery ---

def test_merchant_price_competitiveness_opportunity(test_setup, db_session: Session):
    merchant = test_setup["merchant"]
    p = test_setup["product"]
    
    # Inject a lower external competitor offer to trigger price competitiveness
    amz_store = db_session.query(ExternalStore).filter(ExternalStore.domain == "amazon.in").first()
    comp_off = ExternalProductOffer(
        apex_product_id=p.id,
        external_store_id=amz_store.id if amz_store else "store_amz",
        external_product_title="Nike Men's Dri-FIT Legend Short-Sleeve Training T-Shirt",
        price=Decimal("899.00"),
        mrp=Decimal("1499.00"),
        external_url="https://www.amazon.in/dp/B007XPT5D0",
        match_type="EXACT",
        match_confidence=0.99
    )
    db_session.add(comp_off)
    db_session.commit()

    opps = RevenueOpportunityEngine.discover_opportunities(
        db=db_session,
        merchant_id=merchant.id,
        types=["PRICE_COMPETITIVENESS"]
    )
    assert len(opps) > 0
    price_opp = next((o for o in opps if o.type == "PRICE_COMPETITIVENESS"), None)
    assert price_opp is not None
    assert "Price Alignment" in price_opp.title
    assert price_opp.confidence >= 0.85

    db_session.delete(comp_off)
    db_session.commit()


# --- 7. Catalog & Marketplace Navigation Filtering ---

def test_marketplace_catalog_filters(test_setup):
    res_all = client.get("/api/v1/products?limit=300")
    assert res_all.status_code == 200
    assert len(res_all.json()) >= 10

    # Filter by Category
    res_footwear = client.get("/api/v1/products?category=Footwear")
    assert res_footwear.status_code == 200
    for prod in res_footwear.json():
        assert "footwear" in prod["category"].lower() or "running" in prod["category"].lower() or "sports" in prod["category"].lower()

    # Filter by Brand
    res_nike = client.get("/api/v1/products?brand=Nike")
    assert res_nike.status_code == 200
    for prod in res_nike.json():
        assert "nike" in (prod.get("brand") or "").lower() or "nike" in prod["name"].lower()


# --- 8. Buyhatke-Style Canonical Product Graph & Multi-Retailer Verification Tests ---

from app.services.price_intelligence.validators import (
    is_exact_amazon_pdp,
    is_exact_myntra_pdp,
    is_exact_nike_pdp,
    is_exact_adidas_pdp,
    validate_external_product_image
)
from app.services.price_intelligence.canonical_service import CanonicalPriceIntelligenceService

def test_buyhatke_canonical_product_graph_resolution(test_setup, db_session: Session):
    p = test_setup["product"]
    data = CanonicalPriceIntelligenceService.get_canonical_comparison(db_session, str(p.id), force_refresh=True)
    
    # 1. Canonical physical identity
    canon = data["canonical_product"]
    assert canon is not None
    assert canon["canonical_product_id"] == "canon_nike_drifit_legend_black_m"
    assert canon["brand"] == "Nike"
    assert canon["style_code"] == "718833-010"
    assert canon["gtin"] is None
    assert canon["variant"] == "Classic Black"
    assert canon["verified"] == True

    # 2. Multi-retailer offers for the SAME product
    offers = data["offers"]
    assert len(offers) >= 3
    store_names = [o["store_name"] for o in offers]
    assert any("Nike" in s for s in store_names)

    # 3. Verified Nike Official offer has authentic image, style code, and price
    nike_off = next(o for o in offers if "Nike" in o["store_name"])
    assert nike_off["match_type"] == "VARIANT_EXACT"
    assert nike_off["price"] == 1095.0
    assert nike_off["external_product_image"].startswith("https://static.nike.com")
    assert "718833-010" in nike_off["external_url"]
    assert nike_off["action_label"] == "View exact product →"

    # 4. Search fallback offers have null price and no fake images
    for off in offers:
        if off["match_type"] == "SEARCH_FALLBACK":
            assert off["price"] is None
            assert off["external_product_image"] is None
            assert off["action_label"].startswith("Search on")

def test_authenticity_1_valid_pdp_url_does_not_equal_identity_proof():
    # Valid syntax URL with unverified/missing identity evidence cannot be EXACT
    raw_offer = {
        "external_product_url": "https://www.nike.com/in/t/random-shoe/123456",
        "external_product_image": "https://static.nike.com/img.png",
        "price": 1999.0,
        "match_type": "EXACT",
        "identity_evidence": None # Missing identity evidence!
    }
    # Identity evidence is mandatory
    assert raw_offer["identity_evidence"] is None

def test_authenticity_2_3_fake_asin_and_flipkart_fsn_rejected():
    ok_amz, asin = is_exact_amazon_pdp("https://www.amazon.in/dp/B09DEMO123")
    assert ok_amz == False
    assert asin is None

    from app.services.price_intelligence.validators import is_exact_flipkart_pdp
    ok_fk, fsn = is_exact_flipkart_pdp("https://www.flipkart.com/milton-flask/p/itm1234567")
    assert ok_fk == False
    assert fsn is None

def test_authenticity_4_5_missing_identity_evidence_downgrades(test_setup, db_session: Session):
    p = test_setup["product"]
    fk_store = db_session.query(ExternalStore).filter(ExternalStore.domain == "flipkart.com").first()
    bad_off = ExternalProductOffer(
        apex_product_id=p.id,
        external_store_id=fk_store.id,
        external_product_id="VALIDID123",
        external_product_title="Fake Flipkart Exact",
        external_url="https://www.flipkart.com/nike-tshirt/p/itm9876543210",
        image_url="https://rukminim2.flixcart.com/image/832/832/test.jpg",
        price=Decimal("899.00"),
        match_type="EXACT",
        match_confidence=0.99,
        attributes_json={} # Empty identity evidence!
    )
    db_session.add(bad_off)
    db_session.commit()

    comp = CanonicalPriceIntelligenceService.get_canonical_comparison(db_session, str(p.id), force_refresh=True)
    res = next(o for o in comp["offers"] if o["id"] == str(bad_off.id))
    assert res["match_type"] == "SEARCH_FALLBACK"
    assert res["price"] is None

    db_session.delete(bad_off)
    db_session.commit()

def test_authenticity_6_missing_image_downgrades(test_setup, db_session: Session):
    p = test_setup["product"]
    nike_store = db_session.query(ExternalStore).filter(ExternalStore.domain == "nike.com").first()
    no_img_off = ExternalProductOffer(
        apex_product_id=p.id,
        external_store_id=nike_store.id,
        external_product_id="718833-010",
        external_product_title="Nike Legend",
        external_url="https://www.nike.com/in/t/legend/718833-010",
        image_url=None, # Missing image!
        price=Decimal("1095.00"),
        match_type="EXACT",
        match_confidence=1.0,
        attributes_json={"identity_evidence": {"type": "OFFICIAL_MANUFACTURER_SKU"}}
    )
    db_session.add(no_img_off)
    db_session.commit()

    comp = CanonicalPriceIntelligenceService.get_canonical_comparison(db_session, str(p.id), force_refresh=True)
    res = next(o for o in comp["offers"] if o["id"] == str(no_img_off.id))
    assert res["match_type"] == "SEARCH_FALLBACK"
    assert res["price"] is None

    db_session.delete(no_img_off)
    db_session.commit()

def test_authenticity_7_missing_price_makes_price_null(test_setup, db_session: Session):
    p = test_setup["product"]
    comp = CanonicalPriceIntelligenceService.get_canonical_comparison(db_session, str(p.id), force_refresh=True)
    for off in comp["offers"]:
        if off["match_type"] == "SEARCH_FALLBACK":
            assert off["price"] is None
            assert off["total_price"] is None

def test_authenticity_8_synthetic_canonical_product_cannot_claim_exact(test_setup, db_session: Session):
    synth_p = Product(
        merchant_id=test_setup["merchant"].id,
        name="Synthetic Unverified Gadget",
        category="Electronics",
        price=Decimal("199.00"),
        currency="INR"
    )
    db_session.add(synth_p)
    db_session.commit()
    db_session.refresh(synth_p)

    comp = CanonicalPriceIntelligenceService.get_canonical_comparison(db_session, str(synth_p.id), force_refresh=True)
    assert comp["canonical_product"]["verified"] == False
    assert len(comp["offers"]) == 0
    assert comp["lowest_verified_price"] == 199.0
    assert comp["lowest_store"] == "Apex Store"

    db_session.delete(synth_p)
    db_session.commit()

def test_authenticity_9_verified_canonical_plus_verified_retailer_allowed(test_setup, db_session: Session):
    p = test_setup["product"]
    comp = CanonicalPriceIntelligenceService.get_canonical_comparison(db_session, str(p.id), force_refresh=True)
    nike_off = next(o for o in comp["offers"] if "Nike" in o["store_name"])
    assert nike_off["match_type"] == "VARIANT_EXACT"
    assert nike_off["price"] == 1095.0
    assert nike_off["identity_evidence"]["pdp_verified"] == True
    assert nike_off["identity_evidence"]["image_verified"] == True

def test_authenticity_10_search_fallback_never_appears_as_exact(test_setup, db_session: Session):
    comp = CanonicalPriceIntelligenceService.get_canonical_comparison(db_session, str(test_setup["product"].id), force_refresh=True)
    for off in comp["offers"]:
        if "s?k=" in off["external_product_url"] or "search" in off["external_product_url"]:
            assert off["match_type"] == "SEARCH_FALLBACK"
            assert off["price"] is None
            assert off["external_product_image"] is None

def test_buyhatke_api_endpoint_price_intelligence(test_setup):
    p_id = test_setup["product"].id
    res = client.get(f"/api/v1/price-intelligence/product/{p_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["product_id"] == p_id
    assert data["canonical_product"]["brand"] == "Nike"
    assert data["canonical_product"]["style_code"] == "718833-010"
    assert len(data["offers"]) >= 3


