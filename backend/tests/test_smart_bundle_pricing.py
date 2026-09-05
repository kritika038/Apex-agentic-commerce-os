import pytest
from decimal import Decimal
from sqlalchemy.orm import Session

from app.database.models.merchant import Merchant
from app.database.models.product import Product
from app.database.models.inventory import Inventory
from app.database.models.cart import Cart, CartItem
from app.services.product_affinity_service import ProductAffinityService

@pytest.fixture
def bundle_catalog(db: Session):
    merchant = db.query(Merchant).first()
    if not merchant:
        merchant = Merchant(
            id="m_bundle_test",
            name="Apex Bundle Store",
            domain="bundlestore.apex.local"
        )
        db.add(merchant)
        db.commit()
        db.refresh(merchant)

    # Clean existing test products
    db.query(Product).filter(Product.merchant_id == merchant.id).delete()
    db.commit()

    # Main Shoe: ₹4,299
    p_main = Product(
        id="prod_shoe_4299",
        merchant_id=merchant.id,
        name="Air Cushion Trail Running Shoes",
        category="Footwear",
        subcategory="Running Shoes",
        price=Decimal("4299.00"),
        mrp=Decimal("4999.00"),
        description="Premium trail shoe",
        is_active=True
    )
    db.add(p_main)
    db.flush()
    db.add(Inventory(product_id=p_main.id, merchant_id=merchant.id, stock_quantity=10, reserved_quantity=0))

    # Accessory 1: Performance Socks ₹399
    p_socks = Product(
        id="prod_socks_399",
        merchant_id=merchant.id,
        name="Performance Running Socks",
        category="Accessories",
        subcategory="Socks",
        price=Decimal("399.00"),
        mrp=Decimal("499.00"),
        description="Anti-blister socks",
        is_active=True
    )
    db.add(p_socks)
    db.flush()
    db.add(Inventory(product_id=p_socks.id, merchant_id=merchant.id, stock_quantity=20, reserved_quantity=0))

    # Accessory 2: Water Bottle ₹699
    p_bottle = Product(
        id="prod_bottle_699",
        merchant_id=merchant.id,
        name="Insulated Stainless Steel Water Bottle",
        category="Accessories",
        subcategory="Hydration",
        price=Decimal("699.00"),
        mrp=Decimal("899.00"),
        description="Vacuum insulated bottle",
        is_active=True
    )
    db.add(p_bottle)
    db.flush()
    db.add(Inventory(product_id=p_bottle.id, merchant_id=merchant.id, stock_quantity=15, reserved_quantity=0))

    # Apparel: Running Shorts ₹1,299
    p_shorts = Product(
        id="prod_shorts_1299",
        merchant_id=merchant.id,
        name="Pro Running Shorts",
        category="Apparel",
        subcategory="Shorts",
        price=Decimal("1299.00"),
        mrp=Decimal("1599.00"),
        description="Breathable running shorts",
        is_active=True
    )
    db.add(p_shorts)
    db.flush()
    db.add(Inventory(product_id=p_shorts.id, merchant_id=merchant.id, stock_quantity=8, reserved_quantity=0))

    # Inactive product: should be excluded
    p_inactive = Product(
        id="prod_inactive_acc",
        merchant_id=merchant.id,
        name="Discontinued Arm Band",
        category="Accessories",
        subcategory="Straps",
        price=Decimal("299.00"),
        is_active=False
    )
    db.add(p_inactive)
    db.flush()
    db.add(Inventory(product_id=p_inactive.id, merchant_id=merchant.id, stock_quantity=5, reserved_quantity=0))

    # Zero stock product: should be excluded
    p_nostock = Product(
        id="prod_nostock_acc",
        merchant_id=merchant.id,
        name="Out of Stock Cap",
        category="Accessories",
        subcategory="Headwear",
        price=Decimal("499.00"),
        is_active=True
    )
    db.add(p_nostock)
    db.flush()
    db.add(Inventory(product_id=p_nostock.id, merchant_id=merchant.id, stock_quantity=0, reserved_quantity=0))

    db.commit()
    return merchant, p_main, p_socks, p_bottle, p_shorts


def test_bundle_returns_valid_numeric_prices(client, db: Session, bundle_catalog):
    merchant, p_main, p_socks, p_bottle, p_shorts = bundle_catalog

    res = client.get(f"/api/v1/personalization/products/{p_main.id}/bundles?merchant_id={merchant.id}")
    assert res.status_code == 200
    bundles = res.json()

    assert len(bundles) >= 2
    for b in bundles:
        # Check target product prices
        assert "target_price" in b
        assert isinstance(b["target_price"], (int, float))
        assert b["target_price"] > 0
        assert not str(b["target_price"]).lower() == "nan"

        # Check bundle totals
        assert "bundle_price" in b
        assert isinstance(b["bundle_price"], (int, float))
        assert b["bundle_price"] > float(p_main.price)
        assert not str(b["bundle_price"]).lower() == "nan"

        # Verify bundle total matches main_price + target_price
        expected_total = round(float(p_main.price) + b["target_price"], 2)
        assert b["bundle_price"] == expected_total

        # Verify target fields
        assert b["target_product_id"] != p_main.id
        assert len(b["target_product_name"]) > 0
        assert len(b["evidence"]) > 0


def test_bundle_total_calculation_exact_amounts(client, db: Session, bundle_catalog):
    merchant, p_main, p_socks, p_bottle, p_shorts = bundle_catalog

    res = client.get(f"/api/v1/personalization/products/{p_main.id}/bundles?merchant_id={merchant.id}")
    assert res.status_code == 200
    bundles = res.json()

    # Find socks bundle
    socks_bundle = next((b for b in bundles if b["target_product_id"] == p_socks.id), None)
    assert socks_bundle is not None
    assert socks_bundle["target_price"] == 399.0
    assert socks_bundle["bundle_price"] == 4698.0  # 4299 + 399
    assert "blister prevention" in socks_bundle["evidence"] or "running shoes" in socks_bundle["evidence"]

    # Find bottle bundle
    bottle_bundle = next((b for b in bundles if b["target_product_id"] == p_bottle.id), None)
    if bottle_bundle:
        assert bottle_bundle["target_price"] == 699.0
        assert bottle_bundle["bundle_price"] == 4998.0  # 4299 + 699


def test_bundle_excludes_inactive_and_zero_stock_items(client, db: Session, bundle_catalog):
    merchant, p_main, p_socks, p_bottle, p_shorts = bundle_catalog

    res = client.get(f"/api/v1/personalization/products/{p_main.id}/bundles?merchant_id={merchant.id}")
    assert res.status_code == 200
    bundles = res.json()

    bundle_ids = [b["target_product_id"] for b in bundles]
    assert "prod_inactive_acc" not in bundle_ids
    assert "prod_nostock_acc" not in bundle_ids


def test_bundle_deduplication(client, db: Session, bundle_catalog):
    merchant, p_main, p_socks, p_bottle, p_shorts = bundle_catalog

    res = client.get(f"/api/v1/personalization/products/{p_main.id}/bundles?merchant_id={merchant.id}")
    assert res.status_code == 200
    bundles = res.json()

    bundle_ids = [b["target_product_id"] for b in bundles]
    assert len(bundle_ids) == len(set(bundle_ids))


def test_invalid_main_product_price_returns_empty_bundle(client, db: Session, bundle_catalog):
    merchant, p_main, p_socks, p_bottle, p_shorts = bundle_catalog

    # Create product with 0 price
    p_zero = Product(
        id="prod_zero_price",
        merchant_id=merchant.id,
        name="Free Sample Item",
        category="Accessories",
        price=Decimal("0.00"),
        is_active=True
    )
    db.add(p_zero)
    db.commit()

    res = client.get(f"/api/v1/personalization/products/{p_zero.id}/bundles?merchant_id={merchant.id}")
    assert res.status_code == 200
    assert res.json() == []


def test_nonexistent_product_returns_empty_bundle(client, db: Session, bundle_catalog):
    merchant, p_main, p_socks, p_bottle, p_shorts = bundle_catalog

    res = client.get(f"/api/v1/personalization/products/non_existent_uuid_12345/bundles?merchant_id={merchant.id}")
    assert res.status_code == 200
    assert res.json() == []


def test_add_both_to_cart_execution(client, db: Session, bundle_catalog):
    merchant, p_main, p_socks, p_bottle, p_shorts = bundle_catalog
    session_id = "sess_bundle_cart_test"

    # 1. Add main shoe
    r1 = client.post("/api/v1/cart/items", json={
        "session_id": session_id,
        "product_id": p_main.id,
        "quantity": 1
    })
    assert r1.status_code == 200

    # 2. Add bundle complementary item (socks)
    r2 = client.post("/api/v1/cart/items", json={
        "session_id": session_id,
        "product_id": p_socks.id,
        "quantity": 1
    })
    assert r2.status_code == 200
    cart = r2.json()

    assert len(cart["items"]) == 2
    item_ids = [it["product_id"] for it in cart["items"]]
    assert p_main.id in item_ids
    assert p_socks.id in item_ids
    assert float(cart["total_amount"]) == 4698.0  # 4299 + 399
