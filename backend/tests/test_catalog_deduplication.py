import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from collections import Counter

from app.database.models.product import Product
from app.database.models.merchant import Merchant
from app.database.models.cart import Cart, CartItem
from scripts.seed import seed_db


@pytest.fixture(autouse=True)
def seeded_db(db: Session):
    seed_db(reset=False, db_session=db)
    return db


def test_no_duplicate_canonical_identity_in_products_api(client: TestClient, db: Session):
    """Requirement 8A, 8D, 8E: API returns each physical product exactly once with 0 duplicates."""
    response = client.get("/api/v1/products?limit=300")
    assert response.status_code == 200
    products = response.json()
    assert len(products) == 52, f"Expected 52 active canonical products in /products, got {len(products)}"

    # Verify no duplicate IDs
    ids = [p["id"] for p in products]
    assert len(ids) == len(set(ids)), f"Duplicate product IDs found: {[k for k, v in Counter(ids).items() if v > 1]}"

    # Verify no duplicate exact product names
    names = [p["name"] for p in products]
    assert len(names) == len(set(names)), f"Duplicate product names found in /products: {[k for k, v in Counter(names).items() if v > 1]}"

    # Verify no duplicate SKUs
    skus = [p["sku"] for p in products if p.get("sku")]
    assert len(skus) == len(set(skus)), f"Duplicate SKUs found: {[k for k, v in Counter(skus).items() if v > 1]}"


def test_no_duplicate_in_agent_catalog_api(client: TestClient):
    """Requirement 8F: Agent catalog API returns distinct products with structured variants."""
    response = client.get("/api/v1/agent/catalog?limit=100")
    assert response.status_code == 200
    data = response.json()
    assert data.get("total") == 52
    products = data.get("products", [])
    assert len(products) == 52, f"Expected 52 products in agent catalog, got {len(products)}"

    names = [p["name"] for p in products]
    assert len(names) == len(set(names)), f"Duplicate products in /agent/catalog: {[k for k, v in Counter(names).items() if v > 1]}"


def test_legitimate_product_variants_preserved(db: Session):
    """Requirement 8B, 8C: Legitimate variant details (e.g. T-Shirt colors & styles) are preserved."""
    tshirt = db.query(Product).filter(Product.name == "Sports Dry-Fit T-Shirt").first()
    assert tshirt is not None
    attrs = tshirt.attributes or {}
    variant_details = attrs.get("variant_details") or {}
    assert len(variant_details) >= 4, "Expected at least 4 legitimate color variants on Sports Dry-Fit T-Shirt"
    assert "Classic Black" in variant_details
    assert "Pure White" in variant_details
    assert "Navy Blue" in variant_details
    assert "Crimson Red" in variant_details


def test_seed_rerun_idempotency_and_zero_duplicates(db: Session):
    """Requirement 8G: Multiple consecutive seed runs produce 0 duplicates."""
    count1 = db.query(Product).filter(Product.is_active == True).count()
    assert count1 == 52, f"Expected 52 active canonical products, got {count1}"

    # Re-run seed twice
    res1 = seed_db(reset=False, db_session=db)
    count2 = db.query(Product).filter(Product.is_active == True).count()

    res2 = seed_db(reset=False, db_session=db)
    count3 = db.query(Product).filter(Product.is_active == True).count()

    assert count1 == count2 == count3 == 52, f"Seed is not idempotent: count1={count1}, count2={count2}, count3={count3}"


def test_inventory_and_pricing_integrity(db: Session):
    """Requirement 8I, 8J: Inventory and pricing remain positive, correct Decimals."""
    active_prods = db.query(Product).filter(Product.is_active == True).all()
    assert len(active_prods) == 52
    for p in active_prods:
        assert p.price > Decimal("0.00"), f"Product {p.name} has invalid price {p.price}"
        assert p.inventory is not None, f"Product {p.name} missing inventory record"
        assert p.inventory.stock_quantity >= 0, f"Product {p.name} has negative stock"


def test_existing_order_relationships_intact(db: Session):
    """Requirement 8H: Cart items referencing products remain valid and accessible."""
    merchant = db.query(Merchant).first()
    product = db.query(Product).filter(Product.is_active == True).first()

    # Create cart and cart item referencing product
    cart = Cart(
        merchant_id=merchant.id,
        session_id="session_test_integrity",
        status="active",
        currency="INR",
        total_amount=product.price
    )
    db.add(cart)
    db.flush()

    cart_item = CartItem(
        cart_id=cart.id,
        product_id=product.id,
        quantity=1,
        unit_price_snapshot=product.price
    )
    db.add(cart_item)
    db.commit()

    # Re-run seed to ensure historical records are unaffected
    seed_db(reset=False, db_session=db)

    saved_item = db.query(CartItem).filter(CartItem.id == cart_item.id).first()
    assert saved_item is not None
    assert saved_item.product_id == product.id
    assert saved_item.product.name == product.name
