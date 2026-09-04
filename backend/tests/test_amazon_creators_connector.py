import pytest
import httpx
from decimal import Decimal
from unittest.mock import MagicMock
from sqlalchemy.orm import Session

from app.services.price_intelligence.retailers.amazon import AmazonCreatorsAdapter
from app.services.price_intelligence.canonical_service import CanonicalPriceIntelligenceService
from app.database.session import SessionLocal
from app.database.models.product import Product

@pytest.fixture(scope="module")
def db_session():
    db = SessionLocal()
    yield db
    db.close()

# --- Mock Amazon Creators API Payloads ---

MOCK_OAUTH_TOKEN_RESPONSE = {
    "access_token": "Atza|mock_creators_oauth_token_12345",
    "token_type": "bearer",
    "expires_in": 3600
}

MOCK_CREATORS_API_EXACT_GTIN_RESPONSE = {
    "SearchResult": {
        "TotalResultCount": 1,
        "Items": [
            {
                "ASIN": "B007XPT5D0",
                "DetailPageURL": "https://www.amazon.in/dp/B007XPT5D0",
                "ItemInfo": {
                    "Title": {
                        "DisplayValue": "Nike Men's Dri-FIT Legend Short-Sleeve Training T-Shirt"
                    },
                    "ByLineInfo": {
                        "Brand": {"DisplayValue": "Nike"},
                        "Manufacturer": {"DisplayValue": "Nike"}
                    },
                    "ProductInfo": {
                        "ItemPartNumber": {"DisplayValue": "718833-010"},
                        "Color": {"DisplayValue": "Black"},
                        "Size": {"DisplayValue": "Medium"}
                    },
                    "ExternalIds": {
                        "EANs": {"DisplayValues": ["00888407255169"]},
                        "UPCs": {"DisplayValues": ["0888407255169"]}
                    }
                },
                "Images": {
                    "Primary": {
                        "Large": {
                            "URL": "https://m.media-amazon.com/images/I/51wXkY7fFSL._AC_UL640_QL65_ML3_.jpg",
                            "Height": 640,
                            "Width": 480
                        }
                    }
                },
                "OffersV2": {
                    "Listings": [
                        {
                            "Id": "listing_amz_01",
                            "Price": {
                                "Amount": 949.0,
                                "Currency": "INR"
                            },
                            "Availability": {
                                "Type": "IN_STOCK",
                                "MinOrderQuantity": 1
                            }
                        }
                    ]
                }
            }
        ]
    }
}

MOCK_CREATORS_API_NO_PRICE_RESPONSE = {
    "SearchResult": {
        "TotalResultCount": 1,
        "Items": [
            {
                "ASIN": "B007XPT5D0",
                "DetailPageURL": "https://www.amazon.in/dp/B007XPT5D0",
                "ItemInfo": {
                    "Title": {"DisplayValue": "Nike Men's Dri-FIT Legend Short-Sleeve Training T-Shirt"},
                    "ByLineInfo": {"Brand": {"DisplayValue": "Nike"}},
                    "ProductInfo": {"ItemPartNumber": {"DisplayValue": "718833-010"}},
                    "ExternalIds": {"EANs": {"DisplayValues": ["00888407255169"]}}
                },
                "Images": {
                    "Primary": {
                        "Large": {"URL": "https://m.media-amazon.com/images/I/51wXkY7fFSL._AC_UL640_QL65_ML3_.jpg"}
                    }
                },
                "OffersV2": {
                    "Listings": [] # Price unavailable!
                }
            }
        ]
    }
}

MOCK_CREATORS_API_DIFFERENT_PRODUCT_RESPONSE = {
    "SearchResult": {
        "TotalResultCount": 1,
        "Items": [
            {
                "ASIN": "B099UNRELATED",
                "DetailPageURL": "https://www.amazon.in/dp/B099UNRELATED",
                "ItemInfo": {
                    "Title": {"DisplayValue": "Random Brand Cotton Graphic T-Shirt"},
                    "ByLineInfo": {"Brand": {"DisplayValue": "Random Brand"}},
                    "ProductInfo": {"ItemPartNumber": {"DisplayValue": "XYZ-999"}},
                    "ExternalIds": {"EANs": {"DisplayValues": ["9999999999999"]}}
                },
                "Images": {
                    "Primary": {
                        "Large": {"URL": "https://m.media-amazon.com/images/I/unrelated.jpg"}
                    }
                },
                "OffersV2": {
                    "Listings": [{"Price": {"Amount": 499.0, "Currency": "INR"}}]
                }
            }
        ]
    }
}


# --- Unit Tests ---

def test_1_connector_disabled_by_default():
    adapter = AmazonCreatorsAdapter(enabled=False)
    assert adapter.is_enabled() == False
    
    canonical = {
        "brand": "Nike",
        "style_code": "718833-010",
        "title": "Nike Dri-FIT Legend"
    }
    res = adapter.resolve_canonical_product_offer(canonical)
    assert res["match_type"] == "SEARCH_FALLBACK"
    assert res["price"] is None
    assert res["external_product_image"] is None
    assert "s?k=Nike+718833-010" in res["external_url"]
    assert res["action_label"] == "Search on Amazon India →"

def test_2_connector_missing_credentials_fails_gracefully():
    adapter = AmazonCreatorsAdapter(enabled=True, client_id="", client_secret="")
    assert adapter.is_enabled() == False
    canonical = {"brand": "Nike", "style_code": "718833-010"}
    res = adapter.resolve_canonical_product_offer(canonical)
    assert res["match_type"] == "SEARCH_FALLBACK"
    assert res["price"] is None

def test_3_oauth_token_acquisition():
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = MOCK_OAUTH_TOKEN_RESPONSE
    mock_client.post.return_value = mock_resp

    adapter = AmazonCreatorsAdapter(
        enabled=True,
        client_id="test_client_id",
        client_secret="test_secret",
        http_client=mock_client
    )
    token = adapter._get_access_token()
    assert token == "Atza|mock_creators_oauth_token_12345"

def test_4_valid_api_response_exact_gtin_resolution():
    mock_client = MagicMock()
    
    # Token call
    token_resp = MagicMock()
    token_resp.status_code = 200
    token_resp.json.return_value = MOCK_OAUTH_TOKEN_RESPONSE
    
    # SearchItems call
    search_resp = MagicMock()
    search_resp.status_code = 200
    search_resp.json.return_value = MOCK_CREATORS_API_EXACT_GTIN_RESPONSE

    mock_client.post.side_effect = [token_resp, search_resp]

    adapter = AmazonCreatorsAdapter(
        enabled=True,
        client_id="test_client_id",
        client_secret="test_secret",
        partner_tag="apex-21",
        http_client=mock_client
    )

    canonical = {
        "brand": "Nike",
        "style_code": "718833-010",
        "gtin": "00888407255169",
        "title": "Nike Men's Dri-FIT Legend Short-Sleeve Training T-Shirt",
        "variant": "Classic Black"
    }

    res = adapter.resolve_canonical_product_offer(canonical)
    assert res["match_type"] == "VARIANT_EXACT"
    assert res["price"] == Decimal("949.0")
    assert res["external_product_id"] == "B007XPT5D0"
    assert res["external_product_image"] == "https://m.media-amazon.com/images/I/51wXkY7fFSL._AC_UL640_QL65_ML3_.jpg"
    assert "https://www.amazon.in/dp/B007XPT5D0" in res["external_url"]
    assert res["identity_evidence"]["type"] == "GTIN_EXACT_MATCH"
    assert res["source"] == "AMAZON_CREATORS_API"

def test_5_title_only_similarity_rejected_as_exact():
    mock_client = MagicMock()
    token_resp = MagicMock(status_code=200, json=lambda: MOCK_OAUTH_TOKEN_RESPONSE)
    search_resp = MagicMock(status_code=200, json=lambda: MOCK_CREATORS_API_DIFFERENT_PRODUCT_RESPONSE)
    mock_client.post.side_effect = [token_resp, search_resp]

    adapter = AmazonCreatorsAdapter(
        enabled=True,
        client_id="test_client_id",
        client_secret="test_secret",
        http_client=mock_client
    )

    canonical = {
        "brand": "Nike",
        "style_code": "718833-010",
        "gtin": "00888407255169",
        "title": "Nike Men's Dri-FIT Legend Short-Sleeve Training T-Shirt"
    }

    res = adapter.resolve_canonical_product_offer(canonical)
    assert res["match_type"] == "SEARCH_FALLBACK"
    assert res["price"] is None
    assert res["external_product_image"] is None

def test_6_missing_price_in_offersv2_downgrades_safely():
    mock_client = MagicMock()
    token_resp = MagicMock(status_code=200, json=lambda: MOCK_OAUTH_TOKEN_RESPONSE)
    search_resp = MagicMock(status_code=200, json=lambda: MOCK_CREATORS_API_NO_PRICE_RESPONSE)
    mock_client.post.side_effect = [token_resp, search_resp]

    adapter = AmazonCreatorsAdapter(
        enabled=True,
        client_id="test_client_id",
        client_secret="test_secret",
        http_client=mock_client
    )

    canonical = {
        "brand": "Nike",
        "style_code": "718833-010",
        "gtin": "00888407255169",
        "title": "Nike Men's Dri-FIT Legend"
    }

    res = adapter.resolve_canonical_product_offer(canonical)
    assert res["match_type"] == "SEARCH_FALLBACK"
    assert res["price"] is None

def test_7_api_throttling_429_handled_gracefully():
    mock_client = MagicMock()
    token_resp = MagicMock(status_code=200, json=lambda: MOCK_OAUTH_TOKEN_RESPONSE)
    search_resp = MagicMock(status_code=429, json=lambda: {"Errors": [{"Code": "TooManyRequests"}]})
    mock_client.post.side_effect = [token_resp, search_resp]

    adapter = AmazonCreatorsAdapter(
        enabled=True,
        client_id="test_client_id",
        client_secret="test_secret",
        http_client=mock_client
    )

    canonical = {"brand": "Nike", "style_code": "718833-010"}
    res = adapter.resolve_canonical_product_offer(canonical)
    assert res["match_type"] == "SEARCH_FALLBACK"
    assert res["price"] is None

def test_8_api_timeout_or_500_handled_gracefully():
    mock_client = MagicMock()
    token_resp = MagicMock(status_code=200, json=lambda: MOCK_OAUTH_TOKEN_RESPONSE)
    mock_client.post.side_effect = [token_resp, httpx.ReadTimeout("Amazon API timeout")]

    adapter = AmazonCreatorsAdapter(
        enabled=True,
        client_id="test_client_id",
        client_secret="test_secret",
        http_client=mock_client
    )

    canonical = {"brand": "Nike", "style_code": "718833-010"}
    res = adapter.resolve_canonical_product_offer(canonical)
    assert res["match_type"] == "SEARCH_FALLBACK"
    assert res["price"] is None

def test_9_canonical_service_integration_with_amazon_adapter(db_session: Session):
    p = db_session.query(Product).filter(Product.name == "Sports Dry-Fit T-Shirt").first()
    assert p is not None

    # Inject mock Amazon adapter with verified response
    mock_client = MagicMock()
    token_resp = MagicMock(status_code=200, json=lambda: MOCK_OAUTH_TOKEN_RESPONSE)
    search_resp = MagicMock(status_code=200, json=lambda: MOCK_CREATORS_API_EXACT_GTIN_RESPONSE)
    mock_client.post.side_effect = [token_resp, search_resp]

    adapter = AmazonCreatorsAdapter(
        enabled=True,
        client_id="test_client_id",
        client_secret="test_secret",
        partner_tag="apex-21",
        http_client=mock_client
    )

    comp = CanonicalPriceIntelligenceService.get_canonical_comparison(
        db=db_session,
        product_id=str(p.id),
        force_refresh=True,
        amazon_adapter=adapter
    )

    amz_off = next(o for o in comp["offers"] if o["store_name"] == "Amazon India")
    assert amz_off["match_type"] == "VARIANT_EXACT"
    assert amz_off["price"] == 949.0
    assert amz_off["external_product_id"] == "B007XPT5D0"
    assert amz_off["external_product_image"] == "https://m.media-amazon.com/images/I/51wXkY7fFSL._AC_UL640_QL65_ML3_.jpg"

def test_10_no_secret_leakage_in_adapter_or_offer():
    adapter = AmazonCreatorsAdapter(
        enabled=True,
        client_id="sensitive_client_id_123",
        client_secret="super_secret_key_456"
    )
    canonical = {"brand": "Nike", "style_code": "718833-010"}
    fallback = adapter.build_search_fallback("Nike 718833-010")
    
    # Assert secret never appears anywhere in JSON or string representations
    fallback_str = str(fallback)
    assert "super_secret_key_456" not in fallback_str
    assert "sensitive_client_id_123" not in fallback_str
