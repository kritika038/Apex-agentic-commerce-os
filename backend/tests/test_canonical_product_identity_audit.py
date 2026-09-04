import pytest
from decimal import Decimal
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.database.models.product import Product
from app.database.seeds.canonical_catalog import CANONICAL_PRODUCTS_GRAPH
from app.services.price_intelligence.canonical_service import CanonicalPriceIntelligenceService
from app.services.price_intelligence.retailers.amazon import AmazonCreatorsAdapter
from app.services.price_intelligence.validators import (
    validate_retailer_pdp_url,
    validate_external_product_image
)

@pytest.fixture(scope="module")
def db_session():
    db = SessionLocal()
    yield db
    db.close()


def test_1_no_synthetic_gtin_in_database(db_session: Session):
    """Verifies that no sequential synthetic GTINs (e.g. 890123456...) exist in the database."""
    products = db_session.query(Product).all()
    for p in products:
        if p.gtin:
            # Check for sequential placeholder pattern
            assert not p.gtin.startswith("890123456"), f"Synthetic GTIN {p.gtin} found on product {p.name}"


def test_2_verified_real_world_products_have_authentic_identifiers(db_session: Session):
    """Verifies that Nike, Adidas, Puma flagship items possess verified real-world style codes and verified GTINs when valid."""
    # 1. Nike Dri-FIT Legend (Unverified GTIN null, verified style code preserved)
    tshirt = db_session.query(Product).filter(Product.name == "Sports Dry-Fit T-Shirt").first()
    assert tshirt is not None
    assert tshirt.gtin is None
    assert tshirt.model_number == "718833-010"
    assert tshirt.brand == "Nike"

    # 2. Nike Revolution 6
    pro_run = db_session.query(Product).filter(Product.name == "Pro Running Shoes").first()
    assert pro_run is not None
    assert pro_run.gtin == "0195244584285"
    assert pro_run.model_number == "DC3728-003"
    assert pro_run.brand == "Nike"

    # 3. Adidas Duramo Speed
    adidas = db_session.query(Product).filter(Product.name == "SpeedFlow Marathon Shoes").first()
    assert adidas is not None
    assert adidas.gtin == "4066749964179"
    assert adidas.model_number == "IE7263"
    assert adidas.brand == "Adidas"

    # 4. Puma Active Interlock Shorts
    puma = db_session.query(Product).filter(Product.name == "Running Shorts").first()
    assert puma is not None
    assert puma.gtin == "4063697428416"
    assert puma.model_number == "58672801"
    assert puma.brand == "Puma"


def test_3_generic_apex_catalog_only_products_have_null_gtin(db_session: Session):
    """Verifies that unverified synthetic/generic items correctly have NULL GTIN and APEX_CATALOG_ONLY scope."""
    water_bottle = db_session.query(Product).filter(Product.name == "Insulated Stainless Steel Water Bottle").first()
    assert water_bottle is not None
    assert water_bottle.gtin is None
    assert water_bottle.model_number is None

    socks = db_session.query(Product).filter(Product.name == "Performance Socks").first()
    assert socks is not None
    assert socks.gtin is None

    roller = db_session.query(Product).filter(Product.name == "Deep Tissue Foam Recovery Roller").first()
    assert roller is not None
    assert roller.gtin is None


def test_4_apex_catalog_only_cannot_claim_real_world_exact(db_session: Session):
    """Ensures that APEX_CATALOG_ONLY products return zero exact retailer comparison offers."""
    bottle = db_session.query(Product).filter(Product.name == "Insulated Stainless Steel Water Bottle").first()
    assert bottle is not None

    comp = CanonicalPriceIntelligenceService.get_canonical_comparison(db_session, str(bottle.id), force_refresh=True)
    exact_offers = [o for o in comp["offers"] if o["match_type"] in ["VARIANT_EXACT", "EXACT", "MODEL_EXACT"]]
    assert len(exact_offers) == 0
    assert comp["canonical_product"]["verified"] == False


def test_5_identity_matcher_rejects_wrong_gtin():
    adapter = AmazonCreatorsAdapter(enabled=False)
    canonical = {
        "brand": "Nike",
        "style_code": "718833-010",
        "gtin": "00888407255169"
    }
    candidate = {
        "external_product_id": "B0_WRONG",
        "brand": "Nike",
        "style_code": "718833-010",
        "gtin": "00999999999999", # Mismatched GTIN
        "title": "Nike Men's Shirt"
    }

    is_match, match_type, conf, evidence = adapter.verify_identity(canonical, candidate)
    # Different GTIN cannot be exact GTIN match
    assert match_type != "GTIN_EXACT_MATCH"


def test_6_identity_matcher_rejects_wrong_brand():
    adapter = AmazonCreatorsAdapter(enabled=False)
    canonical = {
        "brand": "Nike",
        "style_code": "718833-010",
        "gtin": None
    }
    candidate = {
        "external_product_id": "B0_WRONG_BRAND",
        "brand": "Adidas",
        "style_code": "718833-010",
        "gtin": None,
        "title": "Adidas Shirt 718833-010"
    }

    is_match, match_type, conf, evidence = adapter.verify_identity(canonical, candidate)
    assert is_match == False
    assert match_type == "SEARCH_FALLBACK"


def test_7_identity_matcher_rejects_wrong_style_code():
    adapter = AmazonCreatorsAdapter(enabled=False)
    canonical = {
        "brand": "Nike",
        "style_code": "718833-010",
        "gtin": None
    }
    candidate = {
        "external_product_id": "B0_WRONG_STYLE",
        "brand": "Nike",
        "style_code": "BV6883-010", # Different Nike shirt style
        "gtin": None,
        "title": "Nike Men's Park VII Shirt"
    }

    is_match, match_type, conf, evidence = adapter.verify_identity(canonical, candidate)
    assert is_match == False
    assert match_type == "SEARCH_FALLBACK"


def test_8_image_provenance_rejects_apex_image_reuse():
    apex_img = "https://images.unsplash.com/photo-1503342217505-b0a15ec3261c?w=600&auto=format&fit=crop&q=80"
    # Attempting to supply the Apex image as retailer image
    is_valid, err = validate_external_product_image(apex_img, apex_img)
    assert is_valid == False
    assert "reuse" in err.lower()


def test_9_no_duplicate_canonical_ids_in_graph():
    ids = [item["id"] for item in CANONICAL_PRODUCTS_GRAPH]
    assert len(ids) == len(set(ids)), f"Duplicate canonical ID detected in graph: {ids}"


def test_10_search_resolution_integrity(db_session: Session):
    """Verifies that canonical lookup for specific items resolves to the exact ground truth."""
    # 1. Nike Dri-FIT
    tshirt = db_session.query(Product).filter(Product.name == "Sports Dry-Fit T-Shirt").first()
    comp_tshirt = CanonicalPriceIntelligenceService.get_canonical_comparison(db_session, str(tshirt.id))
    assert comp_tshirt["canonical_product"]["brand"] == "Nike"
    assert comp_tshirt["canonical_product"]["style_code"] == "718833-010"

    # 2. Adidas Duramo Speed
    shoes = db_session.query(Product).filter(Product.name == "SpeedFlow Marathon Shoes").first()
    comp_shoes = CanonicalPriceIntelligenceService.get_canonical_comparison(db_session, str(shoes.id))
    assert comp_shoes["canonical_product"]["brand"] == "Adidas"
    assert comp_shoes["canonical_product"]["style_code"] == "IE7263"
