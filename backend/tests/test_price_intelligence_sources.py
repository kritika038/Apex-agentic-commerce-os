import pytest
from decimal import Decimal
from sqlalchemy.orm import Session

from app.services.price_intelligence.sources.base import SourceType, SourceCapability
from app.services.price_intelligence.sources.d2c import OfficialD2CSource
from app.services.price_intelligence.sources.structured_data import PublicStructuredDataSource
from app.services.price_intelligence.sources.merchant_feed import MerchantFeedSource
from app.services.price_intelligence.sources.search_fallback import SearchFallbackSource
from app.services.price_intelligence.sources.registry import PriceIntelligenceSourceRegistry
from app.services.price_intelligence.canonical_service import CanonicalPriceIntelligenceService
from app.database.session import SessionLocal
from app.database.models.product import Product

@pytest.fixture(scope="module")
def db_session():
    db = SessionLocal()
    yield db
    db.close()


def test_1_source_types_and_capabilities():
    d2c = OfficialD2CSource("Nike", "Nike Official Store", "nike.com")
    assert d2c.source_type == SourceType.OFFICIAL_D2C
    assert d2c.capabilities.requires_credentials == False
    assert d2c.capabilities.supports_price == True
    assert d2c.capabilities.supports_exact_pdp == True

    structured = PublicStructuredDataSource()
    assert structured.source_type == SourceType.PUBLIC_STRUCTURED
    assert structured.capabilities.requires_credentials == False

    feed = MerchantFeedSource("m_123")
    assert feed.source_type == SourceType.MERCHANT_FEED
    assert feed.capabilities.requires_credentials == False

    fallback = SearchFallbackSource("amazon")
    assert fallback.source_type == SourceType.SEARCH_FALLBACK
    assert fallback.capabilities.supports_price == False
    assert fallback.capabilities.supports_images == False


def test_2_official_d2c_source_nike():
    d2c = OfficialD2CSource("Nike", "Nike Official Store", "nike.com")
    canonical = {
        "id": "canon_nike_drifit_legend_black_m",
        "brand": "Nike",
        "style_code": "718833-010",
        "gtin": "00888407255169",
        "title": "Nike Dri-FIT Legend Men's T-Shirt"
    }
    offers = d2c.discover_offers(canonical)
    assert len(offers) == 1
    off = offers[0]
    assert off["match_type"] == "VARIANT_EXACT"
    assert off["price"] == 1095.0
    assert "718833-010" in off["external_product_url"]
    assert "static.nike.com" in off["external_product_image"]
    assert off["source_type"] == "OFFICIAL_D2C"


def test_3_public_structured_json_ld_parsing():
    sample_json_ld = {
        "@context": "https://schema.org/",
        "@type": "Product",
        "name": "Nike Dri-FIT Legend Short Sleeve",
        "image": "https://images.brand.com/pdp/718833-010.jpg",
        "sku": "718833-010",
        "gtin13": "00888407255169",
        "brand": {
            "@type": "Brand",
            "name": "Nike"
        },
        "offers": {
            "@type": "Offer",
            "price": "1095.00",
            "priceCurrency": "INR",
            "availability": "https://schema.org/InStock",
            "url": "https://www.nike.com/in/t/dri-fit-legend-718833-010"
        }
    }

    parsed = PublicStructuredDataSource.parse_json_ld_payload(sample_json_ld, "https://www.nike.com/in/t/dri-fit-legend-718833-010")
    assert parsed is not None
    assert parsed["source_type"] == "PUBLIC_STRUCTURED"
    assert parsed["price"] == 1095.0
    assert parsed["currency"] == "INR"
    assert parsed["gtin"] == "00888407255169"
    assert parsed["style_code"] == "718833-010"
    assert parsed["external_product_image"] == "https://images.brand.com/pdp/718833-010.jpg"
    assert parsed["availability"] == "IN_STOCK"


def test_4_public_structured_json_ld_missing_fields_strict_nulling():
    sample_no_price = {
        "@context": "https://schema.org/",
        "@type": "Product",
        "name": "Nike Dri-FIT Legend",
        "brand": "Nike"
        # No offers, no image, no sku
    }

    parsed = PublicStructuredDataSource.parse_json_ld_payload(sample_no_price, "https://www.nike.com/in/t/item")
    assert parsed is not None
    assert parsed["price"] is None
    assert parsed["external_product_image"] is None
    assert parsed["gtin"] is None
    assert parsed["style_code"] is None


def test_5_merchant_feed_source_labeling():
    feed_src = MerchantFeedSource(merchant_id="merchant_demo_01")
    canonical = {
        "title": "Sports Dry-Fit T-Shirt",
        "brand": "Nike",
        "style_code": "718833-010",
        "gtin": "00888407255169",
        "merchant_feed_offers": [
            {
                "retailer": "local_partner",
                "store_name": "Local Sports Hub",
                "store_domain": "localsportshub.in",
                "price": Decimal("1050.00"),
                "sku": "718833-010",
                "gtin": "00888407255169",
                "image_url": "https://localsportshub.in/images/718833-010.jpg",
                "pdp_url": "https://localsportshub.in/products/718833-010"
            }
        ]
    }

    offers = feed_src.discover_offers(canonical)
    assert len(offers) == 1
    off = offers[0]
    assert off["source_type"] == "MERCHANT_FEED"
    assert off["source"] == "MERCHANT_PROVIDED_FEED"
    assert off["price"] == 1050.0
    assert off["identity_evidence"]["type"] == "MERCHANT_PROVIDED_FEED"


def test_6_search_fallback_invariants():
    amz_fallback = SearchFallbackSource("amazon")
    canonical = {"brand": "Nike", "style_code": "718833-010", "title": "Nike Dri-FIT Legend"}
    offers = amz_fallback.discover_offers(canonical)
    assert len(offers) == 1
    off = offers[0]
    assert off["match_type"] == "SEARCH_FALLBACK"
    assert off["price"] is None
    assert off["external_product_image"] is None
    assert "https://www.amazon.in/s?k=" in off["external_url"]
    assert off["action_label"] == "Search on Amazon India →"


def test_7_source_registry_orchestration(db_session: Session):
    p = db_session.query(Product).filter(Product.name == "Sports Dry-Fit T-Shirt").first()
    assert p is not None

    registry = PriceIntelligenceSourceRegistry()
    comp = CanonicalPriceIntelligenceService.get_canonical_comparison(
        db=db_session,
        product_id=str(p.id),
        force_refresh=True,
        source_registry=registry
    )

    offers = comp["offers"]
    verified = [o for o in offers if o["match_type"] in ["VARIANT_EXACT", "EXACT", "MODEL_EXACT"]]
    fallbacks = [o for o in offers if o["match_type"] not in ["VARIANT_EXACT", "EXACT", "MODEL_EXACT"]]

    # Nike Official is verified
    assert any("Nike" in o["store_name"] and o["price"] == 1095.0 for o in verified)

    # Amazon and Myntra are fallbacks
    assert any("Amazon" in o["store_name"] and o["price"] is None for o in fallbacks)
    assert any("Myntra" in o["store_name"] and o["price"] is None for o in fallbacks)


def test_8_zero_cost_arbitrary_products(db_session: Session):
    verified_products = [
        "Sports Dry-Fit T-Shirt",
        "SpeedFlow Marathon Shoes",
        "Pro Running Shoes"
    ]

    for name in verified_products:
        p = db_session.query(Product).filter(Product.name == name).first()
        assert p is not None, f"Product {name} must exist"
        
        comp = CanonicalPriceIntelligenceService.get_canonical_comparison(db_session, str(p.id), force_refresh=True)
        assert comp["canonical_product"]["verified"] == True
        assert len(comp["offers"]) >= 1

        for o in comp["offers"]:
            if o["match_type"] in ["VARIANT_EXACT", "EXACT", "MODEL_EXACT"]:
                assert o["price"] is not None
                assert o["external_product_image"] is not None
                assert o["identity_evidence"] is not None
            else:
                assert o["price"] is None
                assert o["external_product_image"] is None
                assert "Search on" in o["action_label"]

    # APEX_CATALOG_ONLY product
    bottle = db_session.query(Product).filter(Product.name == "Insulated Stainless Steel Water Bottle").first()
    assert bottle is not None
    comp_bottle = CanonicalPriceIntelligenceService.get_canonical_comparison(db_session, str(bottle.id), force_refresh=True)
    assert comp_bottle["canonical_product"]["verified"] == False
    assert len(comp_bottle["offers"]) == 0
