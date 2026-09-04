import pytest
import os
import io
from unittest.mock import patch, MagicMock

from app.services.virtual_tryon.providers.local_fashn import LocalFashnVTONProvider
from app.services.virtual_tryon.providers.fashn import FashnVirtualTryOnProvider
from app.services.virtual_tryon.registry import VTOProviderRegistry
from app.services.virtual_tryon.base import VirtualTryOnProvider

# Minimal valid 1x1 JPEG image bytes
VALID_JPEG_BYTES = (
    b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00'
    b'\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t'
    b'\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a'
    b'\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342'
    b'\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00'
    b'\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00'
    b'\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b'
    b'\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9'
) * 2

def test_local_fashn_provider_instantiation_and_properties():
    provider = LocalFashnVTONProvider()
    assert isinstance(provider, VirtualTryOnProvider)
    assert provider.provider_id == "local_fashn"
    assert provider.is_demo is False
    assert provider.is_available is True

def test_local_fashn_provider_missing_weights_unavailable():
    provider = LocalFashnVTONProvider(weights_dir="/non/existent/weights/directory")
    assert provider.is_available is False

def test_registry_resolves_local_fashn_aliases():
    for alias in ["local_fashn", "local", "local_vton", "local-vton", "fashn-vton-1.5"]:
        prov = VTOProviderRegistry.get_provider(alias)
        assert isinstance(prov, LocalFashnVTONProvider)
        assert prov.provider_id == "local_fashn"
        assert prov.is_demo is False

def test_registry_preserves_hosted_fashn_provider():
    for alias in ["fashn", "hosted_fashn", "hosted", "production", "live", "tryon-v1.6"]:
        prov = VTOProviderRegistry.get_provider(alias)
        assert isinstance(prov, FashnVirtualTryOnProvider)
        assert prov.provider_id == "fashn"

def test_local_provider_does_not_require_fashn_api_key(monkeypatch):
    monkeypatch.delenv("FASHN_API_KEY", raising=False)
    provider = LocalFashnVTONProvider()
    # Still available based on local weights and runtime
    assert provider.is_available is True

def test_local_provider_category_mapping():
    provider = LocalFashnVTONProvider()
    
    # Tops
    assert provider._map_category("CLOTHING", {"name": "Sports Dry-Fit T-Shirt", "category": "Apparel", "subcategory": "T-Shirts"}) == "tops"
    assert provider._map_category("CLOTHING", {"name": "Classic Hoodie", "category": "Apparel", "subcategory": "Sweaters"}) == "tops"
    
    # Bottoms
    assert provider._map_category("CLOTHING", {"name": "Denim Jeans", "category": "Apparel", "subcategory": "Pants"}) == "bottoms"
    assert provider._map_category("CLOTHING", {"name": "Athletic Shorts", "category": "Apparel", "subcategory": "Shorts"}) == "bottoms"
    assert provider._map_category("CLOTHING", {"name": "Track Pants", "category": "Apparel", "subcategory": "Trousers"}) == "bottoms"
    
    # One-pieces
    assert provider._map_category("CLOTHING", {"name": "Summer Floral Dress", "category": "Apparel", "subcategory": "Dresses"}) == "one-pieces"
    assert provider._map_category("CLOTHING", {"name": "Silk Kurta", "category": "Apparel", "subcategory": "Ethnic"}) == "one-pieces"
    assert provider._map_category("CLOTHING", {"name": "Lounge Jumpsuit", "category": "Apparel", "subcategory": "Jumpsuits"}) == "one-pieces"

def test_local_provider_rejects_invalid_person_image():
    provider = LocalFashnVTONProvider()
    
    # Empty
    success, data, err_code, err_msg = provider.generate_try_on(
        person_image_bytes=b"",
        product_image_url="https://images.unsplash.com/photo-1503342217505-b0a15ec3261c",
        garment_type="CLOTHING",
        product_metadata={"name": "T-Shirt", "category": "Apparel"}
    )
    assert success is False
    assert err_code == "INVALID_PERSON_IMAGE"
    
    # Corrupt
    success, data, err_code, err_msg = provider.generate_try_on(
        person_image_bytes=b"notanimage" * 50,
        product_image_url="https://images.unsplash.com/photo-1503342217505-b0a15ec3261c",
        garment_type="CLOTHING",
        product_metadata={"name": "T-Shirt", "category": "Apparel"}
    )
    assert success is False
    assert err_code == "INVALID_PERSON_IMAGE"

def test_local_provider_rejects_invalid_garment_url():
    provider = LocalFashnVTONProvider()
    person_bytes = VALID_JPEG_BYTES

    # Missing
    success, data, err_code, err_msg = provider.generate_try_on(
        person_image_bytes=person_bytes,
        product_image_url="",
        garment_type="CLOTHING",
        product_metadata={"name": "T-Shirt", "category": "Apparel"}
    )
    assert success is False
    assert err_code == "INVALID_GARMENT_IMAGE"

    # Unsupported scheme (ftp)
    success, data, err_code, err_msg = provider.generate_try_on(
        person_image_bytes=person_bytes,
        product_image_url="ftp://example.com/photo.jpg",
        garment_type="CLOTHING",
        product_metadata={"name": "T-Shirt", "category": "Apparel"}
    )
    assert success is False
    assert err_code == "INVALID_GARMENT_IMAGE"
    assert "scheme" in err_msg.lower()

    # Path traversal outside project bounds
    success, data, err_code, err_msg = provider.generate_try_on(
        person_image_bytes=person_bytes,
        product_image_url="file:///etc/passwd",
        garment_type="CLOTHING",
        product_metadata={"name": "T-Shirt", "category": "Apparel"}
    )
    assert success is False
    assert err_code == "INVALID_GARMENT_IMAGE"
    assert "project" in err_msg.lower() or "authorized" in err_msg.lower()

    # SSRF Localhost / loopback
    success, data, err_code, err_msg = provider.generate_try_on(
        person_image_bytes=person_bytes,
        product_image_url="http://127.0.0.1:8000/secret.jpg",
        garment_type="CLOTHING",
        product_metadata={"name": "T-Shirt", "category": "Apparel"}
    )
    assert success is False
    assert err_code == "INVALID_GARMENT_IMAGE"
    assert "private" in err_msg.lower() or "unauthorized" in err_msg.lower()

def test_local_provider_rejects_byte_identical_echo():
    provider = LocalFashnVTONProvider()
    person_bytes = VALID_JPEG_BYTES
    garment_bytes = VALID_JPEG_BYTES + b"_garment"

    # Mock downloading garment and mock inference returning exactly person_bytes
    with patch.object(provider, "_download_and_validate_garment", return_value=(garment_bytes, None, None)):
        with patch.object(provider, "_run_subprocess_inference", return_value=(True, person_bytes, None, None)):
            with patch.object(provider, "_run_in_process_inference", return_value=(True, person_bytes, None, None)):
                success, data, err_code, err_msg = provider.generate_try_on(
                    person_image_bytes=person_bytes,
                    product_image_url="https://images.unsplash.com/photo-1503342217505-b0a15ec3261c",
                    garment_type="CLOTHING",
                    product_metadata={"name": "T-Shirt", "category": "Apparel"}
                )
                assert success is False
                assert err_code == "VTO_OUTPUT_INVALID"

def test_local_provider_successful_mocked_synthesis():
    provider = LocalFashnVTONProvider()
    person_bytes = VALID_JPEG_BYTES
    garment_bytes = VALID_JPEG_BYTES + b"_garment"
    synthetic_result = VALID_JPEG_BYTES + b"_synthetic_ai_output"

    with patch.object(provider, "_download_and_validate_garment", return_value=(garment_bytes, None, None)):
        with patch.object(provider, "_run_subprocess_inference", return_value=(True, synthetic_result, None, None)):
            with patch.object(provider, "_run_in_process_inference", return_value=(True, synthetic_result, None, None)):
                success, data, err_code, err_msg = provider.generate_try_on(
                    person_image_bytes=person_bytes,
                    product_image_url="https://images.unsplash.com/photo-1503342217505-b0a15ec3261c",
                    garment_type="CLOTHING",
                    product_metadata={"name": "Sports Dry-Fit T-Shirt", "category": "Apparel"}
                )
                assert success is True
                assert data == synthetic_result
                assert err_code is None
                assert err_msg is None
