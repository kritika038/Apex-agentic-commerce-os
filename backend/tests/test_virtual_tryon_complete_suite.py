import os
import io
import json
import base64
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database.session import SessionLocal
from app.database.models.merchant import Merchant
from app.database.models.user import User
from app.database.models.product import Product
from app.database.models.virtual_tryon import VirtualTryOnJob, VirtualTryOnEvent, TryOnGarmentType, TryOnJobStatus
from app.services.virtual_tryon.service import VirtualTryOnService
from app.services.virtual_tryon.registry import VTOProviderRegistry
from app.services.virtual_tryon.providers.local_fashn import LocalFashnVTONProvider
from app.services.virtual_tryon.providers.fashn import FashnVirtualTryOnProvider
from app.core.security import create_access_token

client = TestClient(app)

def make_valid_jpeg_bytes(marker=b"\xa5") -> bytes:
    header = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00"
    payload = (
        b"\xff\xdb\x00C\x00" + b"\x08" * 64 +
        b"\xff\xc0\x00\x11\x08\x00\xc8\x00\xc8\x03\x01\x11\x00\x02\x11\x01\x03\x11\x01" +
        b"\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b" +
        b"\xff\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00?\x00" + (marker * 1024)
    )
    return header + payload + b"\xff\xd9"

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def catalog_setup(db_session: Session):
    merchant = db_session.query(Merchant).first()
    if not merchant:
        merchant = Merchant(name="Apex Store", email="store@apex.test")
        db_session.add(merchant)
        db_session.commit()
        db_session.refresh(merchant)

    # 1. Apparel - T-Shirt
    tshirt = Product(
        merchant_id=merchant.id,
        name="Sports Dry-Fit T-Shirt",
        brand="Nike",
        category="Apparel",
        subcategory="T-Shirts",
        price=Decimal("999.00"),
        image_url="https://images.unsplash.com/photo-1503342217505-b0a15ec3261c?w=600",
        attributes={
            "color": "Classic Black",
            "size": "Medium",
            "vto_image_ready": True,
            "vto_image_url": "https://images.unsplash.com/photo-1503342217505-b0a15ec3261c?w=600",
            "variant_images": {
                "Classic Black": "https://images.unsplash.com/photo-1503342217505-b0a15ec3261c?w=600",
                "Pure White": "https://images.unsplash.com/photo-1581655353564-df123a1eb820?w=600",
                "Navy Blue": "https://images.unsplash.com/photo-1583743814966-8936f5b7be1a?w=600",
                "Crimson Red": "https://images.unsplash.com/photo-1618354691438-25bc04584c23?w=600"
            },
            "variant_details": {
                "Classic Black": {
                    "color": "Classic Black",
                    "style_code": "718833-010",
                    "gtin": None,
                    "garment_image_url": "https://images.unsplash.com/photo-1503342217505-b0a15ec3261c?w=600",
                    "vto_eligible": True
                },
                "Pure White": {
                    "color": "Pure White",
                    "style_code": "718833-100",
                    "gtin": None,
                    "garment_image_url": "https://images.unsplash.com/photo-1581655353564-df123a1eb820?w=600",
                    "vto_eligible": True
                },
                "Navy Blue": {
                    "color": "Navy Blue",
                    "style_code": "718833-451",
                    "gtin": None,
                    "garment_image_url": "https://images.unsplash.com/photo-1583743814966-8936f5b7be1a?w=600",
                    "vto_eligible": True
                },
                "Crimson Red": {
                    "color": "Crimson Red",
                    "style_code": "718833-657",
                    "gtin": None,
                    "garment_image_url": "https://images.unsplash.com/photo-1618354691438-25bc04584c23?w=600",
                    "vto_eligible": True
                }
            }
        },
        is_active=True
    )
    db_session.add(tshirt)

    # 2. Apparel - Bottoms (Shorts/Pants)
    bottoms = Product(
        merchant_id=merchant.id,
        name="Running Shorts",
        brand="Puma",
        category="Apparel",
        subcategory="Shorts",
        price=Decimal("1299.00"),
        image_url="https://images.unsplash.com/photo-1591195853828-11db59a44f6b?w=600",
        is_active=True
    )
    db_session.add(bottoms)

    # 3. Apparel - One-Piece (Dress)
    dress = Product(
        merchant_id=merchant.id,
        name="Athletic Tennis Dress",
        brand="Adidas",
        category="Apparel",
        subcategory="Dresses",
        price=Decimal("2499.00"),
        image_url="https://images.unsplash.com/photo-1515372039744-b8f02a3ae446?w=600",
        is_active=True
    )
    db_session.add(dress)

    # 4. Footwear - Shoes (Unsupported)
    shoes = Product(
        merchant_id=merchant.id,
        name="Pro Running Shoes",
        brand="Nike",
        category="Footwear",
        subcategory="Running Shoes",
        price=Decimal("3499.00"),
        image_url="https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600",
        is_active=True
    )
    db_session.add(shoes)

    # 5. Electronics - Watch (Unsupported)
    watch = Product(
        merchant_id=merchant.id,
        name="Fitness Tracker Watch",
        brand="Noise",
        category="Electronics",
        subcategory="Smart Watches",
        price=Decimal("8500.00"),
        image_url="https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600",
        is_active=True
    )
    db_session.add(watch)

    # 6. Bag (Unsupported)
    bag = Product(
        merchant_id=merchant.id,
        name="Gym Duffle Bag",
        brand="Under Armour",
        category="Bags",
        subcategory="Gym Bags",
        price=Decimal("1999.00"),
        image_url="https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=600",
        is_active=True
    )
    db_session.add(bag)

    # 7. Bottle (Unsupported)
    bottle = Product(
        merchant_id=merchant.id,
        name="Insulated Steel Water Bottle",
        brand="Apex",
        category="Accessories",
        subcategory="Water Bottles",
        price=Decimal("799.00"),
        image_url="https://images.unsplash.com/photo-1602143407151-7111542de6e8?w=600",
        is_active=True
    )
    db_session.add(bottle)

    db_session.commit()
    db_session.refresh(tshirt)
    db_session.refresh(bottoms)
    db_session.refresh(dress)
    db_session.refresh(shoes)
    db_session.refresh(watch)
    db_session.refresh(bag)
    db_session.refresh(bottle)

    return {
        "merchant": merchant,
        "tshirt": tshirt,
        "bottoms": bottoms,
        "dress": dress,
        "shoes": shoes,
        "watch": watch,
        "bag": bag,
        "bottle": bottle
    }

# 1. Apparel product -> VTO eligible
def test_apparel_product_is_vto_eligible(catalog_setup):
    res = VirtualTryOnService.is_virtual_tryon_supported(catalog_setup["tshirt"])
    assert res.supported is True
    assert res.garment_type == "CLOTHING"

# 2. T-shirt -> category "tops"
def test_tshirt_maps_to_tops_category(catalog_setup):
    provider = LocalFashnVTONProvider()
    cat = provider._map_category("CLOTHING", {
        "name": catalog_setup["tshirt"].name,
        "category": catalog_setup["tshirt"].category,
        "subcategory": catalog_setup["tshirt"].subcategory
    })
    assert cat == "tops"

# 3. Bottoms -> category "bottoms"
def test_bottoms_maps_to_bottoms_category(catalog_setup):
    provider = LocalFashnVTONProvider()
    cat = provider._map_category("CLOTHING", {
        "name": catalog_setup["bottoms"].name,
        "category": catalog_setup["bottoms"].category,
        "subcategory": catalog_setup["bottoms"].subcategory
    })
    assert cat == "bottoms"

# 4. One-piece -> category "one-pieces"
def test_dress_maps_to_one_pieces_category(catalog_setup):
    provider = LocalFashnVTONProvider()
    cat = provider._map_category("CLOTHING", {
        "name": catalog_setup["dress"].name,
        "category": catalog_setup["dress"].category,
        "subcategory": catalog_setup["dress"].subcategory
    })
    assert cat == "one-pieces"

# 5. Shoes -> VTO unavailable
def test_shoes_vto_unavailable(catalog_setup):
    res = VirtualTryOnService.is_virtual_tryon_supported(catalog_setup["shoes"])
    assert res.supported is False
    assert "supports apparel only" in res.reason.lower() or "not in an eligible clothing" in res.reason.lower()

# 6. Watch -> VTO unavailable
def test_watch_vto_unavailable(catalog_setup):
    res = VirtualTryOnService.is_virtual_tryon_supported(catalog_setup["watch"])
    assert res.supported is False

# 7. Bag -> VTO unavailable
def test_bag_vto_unavailable(catalog_setup):
    res = VirtualTryOnService.is_virtual_tryon_supported(catalog_setup["bag"])
    assert res.supported is False

# 8. Bottle -> VTO unavailable
def test_bottle_vto_unavailable(catalog_setup):
    res = VirtualTryOnService.is_virtual_tryon_supported(catalog_setup["bottle"])
    assert res.supported is False

# 9. Exact selected color/variant resolves exact garment image and canonical style code
def test_variant_integrity_resolution(db_session: Session, catalog_setup):
    tshirt = catalog_setup["tshirt"]
    person_bytes = make_valid_jpeg_bytes(marker=b"\x01")
    dummy_out = make_valid_jpeg_bytes(marker=b"\x99")

    variant_expectations = [
        ("Classic Black", "718833-010", "photo-1503342217505-b0a15ec3261c"),
        ("Pure White", "718833-100", "photo-1581655353564-df123a1eb820"),
        ("Navy Blue", "718833-451", "photo-1583743814966-8936f5b7be1a"),
        ("Crimson Red", "718833-657", "photo-1618354691438-25bc04584c23"),
    ]

    for variant_name, expected_style_code, expected_img_substr in variant_expectations:
        with patch.object(LocalFashnVTONProvider, "generate_try_on", return_value=(True, dummy_out, None, None)) as mock_gen:
            job = VirtualTryOnService.create_and_execute_job(
                db=db_session,
                user_id=None,
                session_id=f"test_session_{variant_name.replace(' ', '_')}",
                product_id=str(tshirt.id),
                variant_id=variant_name,
                file_bytes=person_bytes,
                content_type="image/jpeg",
                consent_given=True
            )
            assert job.status == TryOnJobStatus.COMPLETED
            assert expected_img_substr in job.product_image_url
            assert job.variant_metadata.get("style_code") == expected_style_code
            assert job.variant_metadata.get("color") == variant_name
            assert mock_gen.called
            assert expected_img_substr in mock_gen.call_args[1]["product_image_url"]
            assert mock_gen.call_args[1]["product_metadata"]["style_code"] == expected_style_code

# 9b. Negative Test: Navy Blue must NEVER resolve to Black asset or 718833-010
def test_navy_blue_never_resolves_to_black_asset(catalog_setup):
    tshirt = catalog_setup["tshirt"]
    img_url, meta = VirtualTryOnService.resolve_variant_garment(tshirt, "Navy Blue")
    
    assert "photo-1583743814966-8936f5b7be1a" in img_url
    assert "photo-1503342217505-b0a15ec3261c" not in img_url
    assert meta["color"] == "Navy Blue"
    assert meta["color"] != "Classic Black"
    assert meta["style_code"] == "718833-451"
    assert meta["style_code"] != "718833-010"

# 9c. Negative Test: Unverified variant refuses generation with truthful error
def test_unverified_variant_refuses_vto_generation(db_session: Session, catalog_setup):
    tshirt = catalog_setup["tshirt"]
    person_bytes = make_valid_jpeg_bytes(marker=b"\x02")

    with pytest.raises(ValueError) as exc_info:
        VirtualTryOnService.create_and_execute_job(
            db=db_session,
            user_id=None,
            session_id="test_session_unverified_variant",
            product_id=str(tshirt.id),
            variant_id="Neon Green",
            file_bytes=person_bytes,
            content_type="image/jpeg",
            consent_given=True
        )
    assert "AI Try-On unavailable for this variant" in str(exc_info.value)

# 10. File validation produces valid internal storage key
def test_upload_file_validation_and_storage():
    person_bytes = make_valid_jpeg_bytes()
    valid, key, err = VirtualTryOnService.validate_and_save_upload(person_bytes, "image/jpeg")
    assert valid is True
    assert key is not None
    assert err is None
    
    # Path traversal protection
    path = VirtualTryOnService.get_media_path(f"../../../etc/passwd")
    assert path is None or not os.path.isabs(path)

# 11. Local FASHN provider is selected by default when available
def test_local_fashn_provider_selection():
    provider = VTOProviderRegistry.get_provider()
    assert isinstance(provider, LocalFashnVTONProvider)
    assert provider.provider_id == "local_fashn"
    assert provider.is_demo is False

# 12. Provider unavailable -> honest unavailable state
def test_unavailable_provider_reports_honest_state():
    bad_provider = LocalFashnVTONProvider(weights_dir="/non/existent/path")
    assert bad_provider.is_available is False
    success, res, code, msg = bad_provider.generate_try_on(
        person_image_bytes=make_valid_jpeg_bytes(),
        product_image_url="https://img.test/shirt.jpg",
        garment_type="CLOTHING",
        product_metadata={"name": "Shirt", "category": "Apparel"}
    )
    assert success is False
    assert code in ["MODEL_WEIGHTS_NOT_FOUND", "LOCAL_VTO_NOT_CONFIGURED"]

# 13. Generated result cannot be byte-identical to person input
def test_reject_byte_identical_person_input(db_session: Session, catalog_setup):
    tshirt = catalog_setup["tshirt"]
    person_bytes = make_valid_jpeg_bytes(marker=b"\x55")

    with patch.object(LocalFashnVTONProvider, "generate_try_on", return_value=(True, person_bytes, None, None)):
        job = VirtualTryOnService.create_and_execute_job(
            db=db_session,
            user_id=None,
            session_id="test_echo_rejection",
            product_id=str(tshirt.id),
            variant_id="Classic Black",
            file_bytes=person_bytes,
            content_type="image/jpeg",
            consent_given=True
        )
        assert job.status == TryOnJobStatus.FAILED
        assert job.error_code == "IDENTICAL_OUTPUT_REJECTED"

# 14. Failed inference -> honest error state in API
def test_api_failed_inference_returns_honest_error(catalog_setup):
    tshirt = catalog_setup["tshirt"]
    person_bytes = make_valid_jpeg_bytes(marker=b"\x77")

    with patch.object(LocalFashnVTONProvider, "generate_try_on", return_value=(False, None, "GPU_OUT_OF_MEMORY", "GPU VRAM exhausted")):
        res = client.post(
            "/api/v1/virtual-tryon/jobs",
            data={
                "product_id": str(tshirt.id),
                "consent": "true",
                "variant_id": "Classic Black"
            },
            files={"photo": ("user.jpg", io.BytesIO(person_bytes), "image/jpeg")}
        )
        assert res.status_code == 200
        job_id = res.json()["job_id"]
        assert res.json()["status"] == "FAILED"

        status_res = client.get(f"/api/v1/virtual-tryon/jobs/{job_id}")
        assert status_res.status_code == 200
        data = status_res.json()
        assert data["status"] == "FAILED"
        assert data["error_code"] == "GPU_OUT_OF_MEMORY"
        assert "GPU VRAM exhausted" in data["error_message"]

# 15. Canonical GTIN Validation Tests
def test_invalid_gtin_checksum_fails_and_is_not_verified():
    from app.services.price_intelligence.validators import validate_gtin_checksum
    # Invalid check digit strings
    assert validate_gtin_checksum("00888407255169") is False
    assert validate_gtin_checksum("00888407255466") is False
    assert validate_gtin_checksum("00888407255770") is False
    assert validate_gtin_checksum("00888407256081") is False
    assert validate_gtin_checksum("1234567890123") is False
    assert validate_gtin_checksum("invalid-gtin") is False
    assert validate_gtin_checksum("") is False
    assert validate_gtin_checksum(None) is False

def test_valid_gtin_checksum_passes():
    from app.services.price_intelligence.validators import validate_gtin_checksum
    # Known authentic GS1-valid GTINs
    assert validate_gtin_checksum("4063697428416") is True  # Puma shorts
    assert validate_gtin_checksum("0012345678905") is True  # Standard GS1 example

# 16. Missing/null GTIN does not break VTO and preserves variant asset resolution
def test_missing_gtin_does_not_break_vto(db_session: Session, catalog_setup):
    tshirt = catalog_setup["tshirt"]
    # Explicitly set gtin to None
    tshirt.gtin = None
    db_session.commit()

    dummy_out = make_valid_jpeg_bytes(marker=b"\x88")
    with patch.object(LocalFashnVTONProvider, "generate_try_on", return_value=(True, dummy_out, None, None)):
        job = VirtualTryOnService.create_and_execute_job(
            db=db_session,
            user_id=None,
            session_id="test_null_gtin_vto",
            product_id=str(tshirt.id),
            variant_id="Navy Blue",
            file_bytes=make_valid_jpeg_bytes(marker=b"\x03"),
            content_type="image/jpeg",
            consent_given=True
        )
        assert job.status == TryOnJobStatus.COMPLETED
        assert job.variant_metadata["canonical_gtin"] is None
        assert job.variant_metadata["is_gtin_verified"] is False
        assert job.variant_metadata["canonical_style_code"] == "718833-451"
        assert job.variant_metadata["is_style_code_verified"] is True
        assert "photo-1583743814966-8936f5b7be1a" in job.product_image_url

# 17. Variant Resolver cleanly distinguishes style, gtin, variant_id, and garment_asset
def test_variant_resolver_distinguishes_style_gtin_variant_asset(catalog_setup):
    tshirt = catalog_setup["tshirt"]
    img_url, meta = VirtualTryOnService.resolve_variant_garment(tshirt, "Crimson Red")

    assert meta["variant_id"] == "Crimson Red"
    assert meta["color"] == "Crimson Red"
    assert meta["canonical_style_code"] == "718833-657"
    assert meta["canonical_gtin"] is None
    assert meta["is_gtin_verified"] is False
    assert meta["is_style_code_verified"] is True
    assert meta["garment_asset"] == img_url
    assert "photo-1618354691438-25bc04584c23" in meta["garment_asset"]
