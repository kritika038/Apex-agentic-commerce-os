"""
Batch 1 Comprehensive Verification Suite:
(1) AI Virtual Try-On + Real Processing Progress
(2) AI Price Check / Same-Product Identity + Retailer Image Integrity
"""

import pytest
from unittest.mock import patch
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.database.models.product import Product
from app.database.models.virtual_tryon import VirtualTryOnJob, TryOnJobStatus, TryOnGarmentType
from app.services.virtual_tryon.service import VirtualTryOnService
from app.services.virtual_tryon.audit import audit_vto_catalog
from app.services.virtual_tryon.providers.local_fashn import LocalFashnVTONProvider
from app.services.price_intelligence.canonical_service import CanonicalPriceIntelligenceService
from app.services.price_intelligence.validators import validate_retailer_pdp_url, validate_external_product_image

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

# =====================================================================
# FEATURE 1: AI VIRTUAL TRY-ON TESTS
# =====================================================================

def test_1a_vto_variant_resolution_for_puma_shorts(db_session: Session):
    """
    Validates variant resolution for Puma shorts across all common UI input formats:
    - 'Puma Black'
    - 'Puma Black / Medium'
    - 'Puma Black-Medium'
    - '58672801' (style code)
    """
    puma_shorts = db_session.query(Product).filter(Product.name == "Running Shorts", Product.brand == "Puma").first()
    assert puma_shorts is not None, "Running Shorts product must exist in seed catalog"

    formats = ["Puma Black", "Puma Black / Medium", "Puma Black-Medium", "58672801"]
    for fmt in formats:
        garment_url, meta = VirtualTryOnService.resolve_variant_garment(puma_shorts, fmt)
        assert garment_url is not None, f"Variant resolution failed for format: {fmt}"
        assert "http" in garment_url, f"Garment URL must be valid HTTP URL: {garment_url}"
        assert meta["color"] == "Puma Black" or meta["variant_id"] == fmt

def test_1b_vto_refuses_unverified_variant(db_session: Session):
    """
    Validates that requesting an unverified/unknown variant raises a truthful error.
    """
    puma_shorts = db_session.query(Product).filter(Product.name == "Running Shorts", Product.brand == "Puma").first()
    assert puma_shorts is not None

    with pytest.raises(ValueError) as excinfo:
        VirtualTryOnService.resolve_variant_garment(puma_shorts, "Neon Green / XXL")
    assert "No verified garment asset found" in str(excinfo.value)

def test_1c_vto_deterministic_catalog_coverage_audit(db_session: Session):
    """
    Runs the deterministic catalog coverage audit and verifies 100% readiness across all eligible apparel items.
    """
    audit = audit_vto_catalog(db_session)
    assert audit["total_eligible_clothing_products"] > 0
    assert audit["variants_missing_garment_asset_count"] == 0
    assert audit["invalid_assets_count"] == 0
    assert audit["wrong_variant_mapping_count"] == 0
    assert audit["is_catalog_vto_ready"] is True
    assert audit["coverage_percentage"] == 100.0

def test_1d_vto_job_real_progress_lifecycle(db_session: Session):
    """
    Validates that a VTO job persists stage information, progress percentage,
    and adheres to monotonic clamping during execution.
    """
    nike_tshirt = db_session.query(Product).filter(Product.name == "Sports Dry-Fit T-Shirt").first()
    assert nike_tshirt is not None

    person_bytes = make_valid_jpeg_bytes(marker=b"\x11")
    output_bytes = make_valid_jpeg_bytes(marker=b"\x22")

    def mock_gen_with_progress(**kwargs):
        callback = kwargs.get("progress_callback")
        if callback:
            callback("PREPARING", 10, None, None, "Preparing your photo...")
            callback("GARMENT_VALIDATION", 20, None, None, "Validating selected garment...")
            callback("POSE_DETECTION", 30, None, None, "Detecting pose...")
            callback("GARMENT_PREPARATION", 40, None, None, "Preparing garment...")
            callback("DIFFUSION", 65, 10, 20, "Generating AI try-on...")
            callback("FINALIZING", 95, None, None, "Finalizing result...")
        return (True, output_bytes, None, None)

    with patch.object(LocalFashnVTONProvider, "generate_try_on", side_effect=mock_gen_with_progress):
        job = VirtualTryOnService.create_and_execute_job(
            db=db_session,
            user_id=None,
            session_id="test_sess_123",
            product_id=str(nike_tshirt.id),
            variant_id="Classic Black",
            file_bytes=person_bytes,
            content_type="image/jpeg",
            consent_given=True,
            background=False
        )

        assert job.status == TryOnJobStatus.COMPLETED
        assert job.progress_percent == 100
        assert job.processing_stage == "COMPLETED"
        assert job.progress_message == "Try-on ready"
        assert job.result_image_key is not None

# =====================================================================
# FEATURE 2: AI PRICE CHECK / SAME-PRODUCT IDENTITY & IMAGE INTEGRITY
# =====================================================================

def test_2a_price_check_puma_shorts_canonical_and_external_integrity(db_session: Session):
    """
    Validates Price Intelligence on Puma Shorts:
    - Canonical product is verified
    - Puma Official has direct verified PDP URL and numeric price
    - Amazon Search Fallback has price = null and SEARCH_FALLBACK match type
    - Lowest verified price claims 'among checked stores'
    """
    puma_shorts = db_session.query(Product).filter(Product.name == "Running Shorts", Product.brand == "Puma").first()
    assert puma_shorts is not None

    comp = CanonicalPriceIntelligenceService.get_canonical_comparison(db_session, str(puma_shorts.id), force_refresh=True)

    assert comp["canonical_product"]["verified"] is True
    assert comp["canonical_product"]["brand"] == "Puma"
    assert comp["canonical_product"]["style_code"] == "58672801"

    # Inspect offers
    offers = comp["offers"]
    puma_offer = next((o for o in offers if "puma.com" in o["store_domain"]), None)
    amz_offer = next((o for o in offers if "amazon.in" in o["store_domain"]), None)

    if puma_offer:
        assert puma_offer["match_type"] in ["VARIANT_EXACT", "EXACT", "EXACT_PRODUCT"]
        assert puma_offer["price"] == 1199.0
        assert "in.puma.com" in puma_offer["external_url"]
        assert puma_offer["external_image_url"] is not None
        assert "unsplash" not in (puma_offer["external_image_url"] or "")  # Authenticated brand image, not Apex placeholder

    if amz_offer:
        assert amz_offer["match_type"] == "SEARCH_FALLBACK"
        assert amz_offer["price"] is None
        assert amz_offer["external_image_url"] is None  # Retailer image integrity: NO fake product image

    # Verification Scope
    assert comp["verification_scope"] == "checked_stores_only"
    assert "among checked stores" in comp["summary_text"] or "checked sources" in comp["summary_text"]

def test_2b_price_check_never_copies_apex_image_to_retailer():
    """
    Validates that retailer images cannot reuse the Apex catalog image.
    """
    apex_img = "https://images.unsplash.com/photo-1591195853828-11db59a44f6b?w=600"
    
    # Matching image is rejected
    valid, err = validate_external_product_image(apex_img, apex_img)
    assert valid is False
    assert "cannot reuse" in err.lower() or "canonical image" in err.lower()

    # Independent retailer image is accepted
    retailer_img = "https://images.puma.com/image/upload/586728/01.png"
    valid, err = validate_external_product_image(retailer_img, apex_img)
    assert valid is True
    assert err is None

def test_2c_direct_pdp_url_validation():
    """
    Validates that generic homepage or search URLs are rejected as verified PDPs.
    """
    # Valid Amazon PDP
    valid, asin = validate_retailer_pdp_url("amazon.in", "https://www.amazon.in/dp/B08N5WRWNW")
    assert valid is True
    assert asin == "B08N5WRWNW"

    # Amazon search query rejected as exact PDP
    valid, _ = validate_retailer_pdp_url("amazon.in", "https://www.amazon.in/s?k=Puma+Shorts")
    assert valid is False

    # Amazon homepage rejected
    valid, _ = validate_retailer_pdp_url("amazon.in", "https://www.amazon.in/")
    assert valid is False
