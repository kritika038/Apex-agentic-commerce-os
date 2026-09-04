import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database.session import SessionLocal
from app.database.models.product import Product
from app.database.seeds.marketplace_catalog import BASELINE_PRODUCTS

client = TestClient(app)

@pytest.fixture(scope="module")
def db_session():
    db = SessionLocal()
    yield db
    db.close()

def test_1_storefront_returns_unique_product_families(db_session: Session):
    """Verifies that GET /api/v1/products returns distinct canonical cards without duplicates."""
    response = client.get("/api/v1/products?limit=200")
    assert response.status_code == 200
    products = response.json()
    assert len(products) > 0

    names = [p["name"] for p in products]
    assert len(names) == len(set(names)), f"Duplicate product names in storefront listing: {[n for n in names if names.count(n) > 1]}"

def test_2_legitimate_variants_preserved_in_product_detail(db_session: Session):
    """Verifies that multi-variant items retain their full color/size matrices in PDP."""
    response = client.get("/api/v1/products?limit=200")
    assert response.status_code == 200
    products = response.json()

    # Find Pegasus 40
    pegasus = next((p for p in products if "Pegasus" in p["name"]), None)
    assert pegasus is not None

    pdp_resp = client.get(f"/api/v1/products/{pegasus['id']}")
    assert pdp_resp.status_code == 200
    pdp = pdp_resp.json()

    assert "available_colors" in pdp
    assert len(pdp["available_colors"]) >= 1
    assert "available_sizes" in pdp
    assert len(pdp["available_sizes"]) >= 1

def test_3_distinct_products_remain_separate():
    """Verifies that different shoe models remain separate items."""
    response = client.get("/api/v1/products?limit=200")
    assert response.status_code == 200
    products = response.json()
    names = [p["name"] for p in products]

    assert "Nike Air Zoom Pegasus 40" in names
    assert "Adidas Ultraboost Light 23" in names
    assert "Nike Precision 6 Low Basketball" in names
    assert "Asics Gel-Peake Cricket Spikes" in names

def test_4_pagination_does_not_duplicate():
    """Verifies that pagination does not duplicate items across pages."""
    resp1 = client.get("/api/v1/products?offset=0&limit=10")
    resp2 = client.get("/api/v1/products?offset=10&limit=10")
    assert resp1.status_code == 200
    assert resp2.status_code == 200

    ids1 = {p["id"] for p in resp1.json()}
    ids2 = {p["id"] for p in resp2.json()}
    assert len(ids1.intersection(ids2)) == 0

def test_5_search_filter_does_not_duplicate():
    """Verifies search results contain no duplicate product cards."""
    response = client.get("/api/v1/products?q=Nike&limit=50")
    assert response.status_code == 200
    products = response.json()
    ids = [p["id"] for p in products]
    assert len(ids) == len(set(ids))

def test_6_category_filter_does_not_duplicate():
    """Verifies category filtering contains no duplicate product cards."""
    response = client.get("/api/v1/products?category=Footwear&limit=50")
    assert response.status_code == 200
    products = response.json()
    ids = [p["id"] for p in products]
    assert len(ids) == len(set(ids))

from app.database.seeds.marketplace_catalog import generate_marketplace_products

def test_7_seed_catalog_images_are_grounded_and_valid():
    """Verifies that seed catalog has valid images and no empty URLs."""
    products = generate_marketplace_products()
    for item in products:
        assert item.get("image_url"), f"Product {item.get('name')} is missing image_url"
        assert item["image_url"].startswith("http"), f"Product {item.get('name')} has invalid image URL"
