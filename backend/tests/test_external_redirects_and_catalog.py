import pytest
from decimal import Decimal
from app.services.external_stores.registry import ExternalStoreRegistry, ALLOWED_EXTERNAL_DOMAINS
from app.services.virtual_tryon.service import VirtualTryOnService
from app.database.models.product import Product
from app.database.models.external_store import ExternalStore
from app.database.models.external_offer import ExternalProductOffer, ExternalOutboundClick
from app.database.seeds.marketplace_catalog import generate_marketplace_products, BASELINE_PRODUCTS
from app.services.price_comparison_service import PriceComparisonService

def test_allowed_domain_validation():
    """Verifies that only authorized external merchant domains are permitted."""
    assert ExternalStoreRegistry.is_domain_allowed("https://www.amazon.in/dp/B09DEMO123") is True
    assert ExternalStoreRegistry.is_domain_allowed("https://www.flipkart.com/search?q=running+shoes") is True
    assert ExternalStoreRegistry.is_domain_allowed("https://www.myntra.com/running-shoes") is True
    assert ExternalStoreRegistry.is_domain_allowed("https://www.nike.com/in/t/pegasus") is True
    assert ExternalStoreRegistry.is_domain_allowed("https://adidas.co.in/shoes") is True
    assert ExternalStoreRegistry.is_domain_allowed("https://in.puma.com/men/shoes") is True
    assert ExternalStoreRegistry.is_domain_allowed("https://www.decathlon.in/p/890123") is True

    # Rejection of malicious and open-redirect domains
    assert ExternalStoreRegistry.is_domain_allowed("http://localhost:3000/api/v1") is False
    assert ExternalStoreRegistry.is_domain_allowed("javascript:alert(1)") is False
    assert ExternalStoreRegistry.is_domain_allowed("data:text/html,<html>") is False
    assert ExternalStoreRegistry.is_domain_allowed("https://evil-attacker.com/steal") is False
    assert ExternalStoreRegistry.is_domain_allowed("https://amazon.in.attacker.com/phish") is False
    assert ExternalStoreRegistry.is_domain_allowed("") is False
    assert ExternalStoreRegistry.is_domain_allowed(None) is False

def test_strict_vto_eligibility_apparel_only():
    """Verifies that ONLY clothing/apparel is eligible for VTO; footwear, watches, bottles, etc. are rejected."""
    
    # 1. Supported Apparel
    tshirt = Product(name="Sports Dry-Fit T-Shirt", category="Apparel", subcategory="T-Shirts", image_url="https://img.test/tshirt.jpg", attributes={"vto_image_ready": True})
    res_tshirt = VirtualTryOnService.is_virtual_tryon_supported(tshirt)
    assert res_tshirt.supported is True
    assert res_tshirt.garment_type == "CLOTHING"

    jacket = Product(name="Puma Windbreaker Hooded Running Jacket", category="Fashion", subcategory="Jackets", image_url="https://img.test/jacket.jpg", attributes={"vto_image_ready": True})
    res_jacket = VirtualTryOnService.is_virtual_tryon_supported(jacket)
    assert res_jacket.supported is True
    assert res_jacket.garment_type == "CLOTHING"

    jeans = Product(name="Levi's 511 Slim Fit Stretch Denim Jeans", category="Fashion", subcategory="Jeans", image_url="https://img.test/jeans.jpg", attributes={"vto_image_ready": True})
    res_jeans = VirtualTryOnService.is_virtual_tryon_supported(jeans)
    assert res_jeans.supported is True
    assert res_jeans.garment_type == "CLOTHING"

    # 2. Footwear is strictly UNSUPPORTED for VTO
    shoes = Product(name="Pro Running Shoes", category="Running", subcategory="Running Shoes", image_url="https://img.test/shoes.jpg")
    res_shoes = VirtualTryOnService.is_virtual_tryon_supported(shoes)
    assert res_shoes.supported is False
    assert "supports apparel only" in res_shoes.reason.lower()

    sneakers = Product(name="Puma Smashic Casual Classic Sneakers", category="Fashion", subcategory="Sneakers", image_url="https://img.test/sneakers.jpg")
    res_sneakers = VirtualTryOnService.is_virtual_tryon_supported(sneakers)
    assert res_sneakers.supported is False
    assert "supports apparel only" in res_sneakers.reason.lower()

    # 3. Unsuitable image rejected for VTO
    unready_shirt = Product(name="Graphic Tee", category="Apparel", subcategory="T-Shirts", image_url="https://img.test/portrait.jpg", attributes={"vto_image_ready": False})
    res_unready = VirtualTryOnService.is_virtual_tryon_supported(unready_shirt)
    assert res_unready.supported is False
    assert "not optimized" in res_unready.reason.lower()

    # 4. Explicitly Unsupported Non-Apparel Categories
    bottle = Product(name="Insulated Stainless Steel Water Bottle", category="Accessories", subcategory="Water Bottles", image_url="https://img.test/bot.jpg")
    res_bottle = VirtualTryOnService.is_virtual_tryon_supported(bottle)
    assert res_bottle.supported is False

    watch = Product(name="Fitness Tracker Watch", category="Electronics", subcategory="Smart Watches", image_url="https://img.test/watch.jpg")
    res_watch = VirtualTryOnService.is_virtual_tryon_supported(watch)
    assert res_watch.supported is False

    mat = Product(name="Kimjaly 8mm High-Grip Yoga Mat", category="Sports & Fitness", subcategory="Yoga Mats", image_url="https://img.test/mat.jpg")
    res_mat = VirtualTryOnService.is_virtual_tryon_supported(mat)
    assert res_mat.supported is False

    backpack = Product(name="American Tourister 32L Casual Laptop Backpack", category="Travel", subcategory="Backpacks", image_url="https://img.test/backpack.jpg")
    res_backpack = VirtualTryOnService.is_virtual_tryon_supported(backpack)
    assert res_backpack.supported is False

    earbuds = Product(name="boAt Airdopes 141 ANC Earbuds", category="Electronics", subcategory="Earbuds", image_url="https://img.test/earbuds.jpg")
    res_earbuds = VirtualTryOnService.is_virtual_tryon_supported(earbuds)
    assert res_earbuds.supported is False

    dumbbells = Product(name="Cast Iron Hex Dumbbell Pair 5kg", category="Sports & Fitness", subcategory="Dumbbells", image_url="https://img.test/dumbbells.jpg")
    res_dumbbells = VirtualTryOnService.is_virtual_tryon_supported(dumbbells)
    assert res_dumbbells.supported is False

def test_catalog_seed_data_integrity():
    """Verifies that 100% of seeded products have authoritative brand, title, image, and valid external offers."""
    products = generate_marketplace_products()
    assert len(products) >= 30

    valid_images_count = 0
    vto_ready_count = 0
    non_vto_count = 0

    for p in products:
        assert p.get("name"), f"Missing name for {p}"
        assert p.get("brand"), f"Missing brand for {p['name']}"
        assert p.get("category"), f"Missing category for {p['name']}"
        assert p.get("image_url"), f"Missing image_url for {p['name']}"
        assert p.get("image_url").startswith("https://"), f"Invalid image_url format for {p['name']}"
        assert p.get("price") > Decimal("0"), f"Price must be positive for {p['name']}"
        
        valid_images_count += 1
        
        attrs = p.get("attributes") or {}
        if attrs.get("vto_image_ready"):
            vto_ready_count += 1
        else:
            non_vto_count += 1

        for off in p.get("external_offers", []):
            store_domain = off.get("store_domain")
            assert store_domain, f"Missing store_domain in offer for {p['name']}"
            assert store_domain in ALLOWED_EXTERNAL_DOMAINS, f"Unregistered store domain {store_domain} for {p['name']}"
            if off.get("price") is not None:
                assert off.get("price") > Decimal("0"), f"External price must be positive for {p['name']}"

    assert valid_images_count == len(products)
    assert vto_ready_count > 0
    assert non_vto_count > 0

    # Ensure zero legacy portrait image URLs
    for p in products:
        assert "photo-1521572267360-ee0c2909d518" not in p.get("image_url", ""), f"Legacy portrait found in {p['name']}"
        attrs = p.get("attributes") or {}
        if "variant_images" in attrs:
            for color, img in attrs["variant_images"].items():
                assert "photo-1521572267360-ee0c2909d518" not in img, f"Legacy portrait found in variant {color} of {p['name']}"

def test_tshirt_color_variant_and_external_search_fallback():
    """Verifies that Sports Dry-Fit T-Shirt has black primary image, variant mappings, and exact Amazon + fallback Myntra."""
    products = generate_marketplace_products()
    tshirt = next((p for p in products if "Sports Dry-Fit T-Shirt" in p["name"]), None)
    assert tshirt is not None
    assert tshirt["image_url"] == "https://images.unsplash.com/photo-1503342217505-b0a15ec3261c?w=600&auto=format&fit=crop&q=80"
    
    attrs = tshirt.get("attributes", {})
    assert attrs.get("color") == "Classic Black"
    assert "Classic Black" in attrs.get("variant_images", {})
    assert "Pure White" in attrs.get("variant_images", {})
    assert "Navy Blue" in attrs.get("variant_images", {})
    assert "Crimson Red" in attrs.get("variant_images", {})
    
    # Check external offers: Nike is EXACT_PRODUCT, Amazon/Myntra are SEARCH_FALLBACK
    offers = tshirt.get("external_offers", [])
    nike = next(o for o in offers if o.get("store_domain") == "nike.com")
    assert nike.get("match_type") in ["VARIANT_EXACT", "EXACT", "EXACT_PRODUCT"]
    assert nike.get("price") == Decimal("1095.00")
    assert "718833-010" in nike.get("external_url", "")
    
    amz = next(o for o in offers if o.get("store_domain") == "amazon.in")
    assert amz.get("match_type") == "SEARCH_FALLBACK"
    assert amz.get("price") is None
    
    myn = next(o for o in offers if o.get("store_domain") == "myntra.com")
    assert myn.get("match_type") == "SEARCH_FALLBACK"
    assert myn.get("price") is None
