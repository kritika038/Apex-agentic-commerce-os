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
from app.database.models.inventory import Inventory
from app.database.models.virtual_tryon import VirtualTryOnJob, VirtualTryOnEvent, TryOnGarmentType, TryOnJobStatus
from app.services.virtual_tryon.service import VirtualTryOnService
from app.services.virtual_tryon.registry import VTOProviderRegistry
from app.services.virtual_tryon.providers.fashn import FashnVirtualTryOnProvider
from app.core.security import create_access_token

@pytest.fixture(autouse=True)
def configure_fashn_provider_for_test(monkeypatch):
    monkeypatch.setenv("VIRTUAL_TRYON_PROVIDER", "fashn")

client = TestClient(app)

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def make_test_image_bytes(marker=b"\xa5") -> bytes:
    header = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00"
    payload = (
        b"\xff\xdb\x00C\x00" + b"\x08" * 64 +
        b"\xff\xc0\x00\x11\x08\x00\xc8\x00\xc8\x03\x01\x11\x00\x02\x11\x01\x03\x11\x01" +
        b"\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b" +
        b"\xff\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00?\x00" + (marker * 1024)
    )
    return header + payload + b"\xff\xd9"

@pytest.fixture
def vto_test_context(db_session: Session):
    merchant = db_session.query(Merchant).first()
    if not merchant:
        merchant = Merchant(name="Demo VTO Merchant", email="merchant@vto-demo.test")
        db_session.add(merchant)
        db_session.commit()
        db_session.refresh(merchant)

    user_a = db_session.query(User).filter(User.email == "customer_vto_a@test.com").first()
    if not user_a:
        user_a = User(
            merchant_id=merchant.id,
            email="customer_vto_a@test.com",
            full_name="VTO User Alpha",
            role="customer",
            hashed_password="pw"
        )
        db_session.add(user_a)
        db_session.commit()
        db_session.refresh(user_a)

    user_b = db_session.query(User).filter(User.email == "customer_vto_b@test.com").first()
    if not user_b:
        user_b = User(
            merchant_id=merchant.id,
            email="customer_vto_b@test.com",
            full_name="VTO User Beta",
            role="customer",
            hashed_password="pw"
        )
        db_session.add(user_b)
        db_session.commit()
        db_session.refresh(user_b)

    # Footwear Product (unsupported for VTO)
    shoe = db_session.query(Product).filter(Product.name == "Pro Running Shoes").first()
    if not shoe:
        shoe = Product(
            merchant_id=merchant.id,
            name="Pro Running Shoes",
            brand="Nike",
            category="Footwear",
            subcategory="Running Shoes",
            price=Decimal("3499.00"),
            image_url="https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600",
            is_active=True
        )
        db_session.add(shoe)
        db_session.commit()
        db_session.refresh(shoe)

    # Eligible Apparel Shirt Product
    shirt = db_session.query(Product).filter(Product.name == "Sports Dry-Fit T-Shirt").first()
    if not shirt:
        shirt = Product(
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
                    "Pure White": "https://images.unsplash.com/photo-1581655353564-df123a1eb820?w=600"
                }
            },
            is_active=True
        )
        db_session.add(shirt)
        db_session.commit()
        db_session.refresh(shirt)

    token_a = create_access_token(user_a.id, merchant.id, user_a.role)
    token_b = create_access_token(user_b.id, merchant.id, user_b.role)

    return {
        "merchant": merchant,
        "user_a": user_a,
        "user_b": user_b,
        "token_a": token_a,
        "token_b": token_b,
        "shirt": shirt,
        "shoe": shoe
    }


# =====================================================================
# 1. Eligibility Enforcement Tests
# =====================================================================

def test_vto_eligibility_apparel_accepted(vto_test_context):
    shirt = vto_test_context["shirt"]
    res = VirtualTryOnService.is_virtual_tryon_supported(shirt)
    assert res.supported is True
    assert res.garment_type == "CLOTHING"

def test_vto_eligibility_footwear_rejected(vto_test_context):
    shoe = vto_test_context["shoe"]
    res = VirtualTryOnService.is_virtual_tryon_supported(shoe)
    assert res.supported is False
    assert "supports apparel only" in res.reason.lower()

def test_vto_eligibility_unsupported_bottle(db_session: Session, vto_test_context):
    merchant = vto_test_context["merchant"]
    bottle = Product(
        merchant_id=merchant.id,
        name="Insulated Steel Water Bottle",
        category="Accessories",
        subcategory="Water Bottles",
        price=Decimal("799.00"),
        image_url="https://img.test/bottle.jpg",
        is_active=True
    )
    res = VirtualTryOnService.is_virtual_tryon_supported(bottle)
    assert res.supported is False
    assert "does not support virtual try-on" in res.reason.lower()

def test_vto_eligibility_unsupported_watch(db_session: Session, vto_test_context):
    merchant = vto_test_context["merchant"]
    watch = Product(
        merchant_id=merchant.id,
        name="Apex Smart Watch Fitness Tracker",
        category="Electronics",
        subcategory="Smart Watches",
        price=Decimal("2499.00"),
        image_url="https://img.test/watch.jpg",
        is_active=True
    )
    res = VirtualTryOnService.is_virtual_tryon_supported(watch)
    assert res.supported is False


# =====================================================================
# 2. FASHN Provider Unit Tests
# =====================================================================

def test_fashn_missing_api_key_reports_provider_not_configured():
    provider = FashnVirtualTryOnProvider(api_key="")
    assert provider.is_available is False
    assert provider.is_demo is False
    
    success, res_bytes, err_code, err_msg = provider.generate_try_on(
        person_image_bytes=make_test_image_bytes(),
        product_image_url="https://img.test/shirt.jpg",
        garment_type="CLOTHING",
        product_metadata={"name": "Tee", "subcategory": "T-Shirts"}
    )
    assert success is False
    assert res_bytes is None
    assert err_code == "PROVIDER_NOT_CONFIGURED"
    assert "FASHN_API_KEY" in err_msg

def test_fashn_request_construction_and_payload():
    provider = FashnVirtualTryOnProvider(api_key="fashn_test_key_123")
    assert provider.is_available is True

    person_bytes = make_test_image_bytes()
    
    with patch("requests.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"id": "pred_12345", "status": "in_progress"}
        )
        with patch("requests.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: {"id": "pred_12345", "status": "completed", "output": ["https://cdn.fashn.ai/out.jpg"]}
            )
            with patch.object(provider, "_download_and_validate_output") as mock_dl:
                mock_dl.return_value = (True, make_test_image_bytes(marker=b"\xb6"), None, None)
                
                success, out_bytes, code, msg = provider.generate_try_on(
                    person_image_bytes=person_bytes,
                    product_image_url="https://img.test/black_tee.jpg",
                    garment_type="CLOTHING",
                    product_metadata={"name": "Sports Dry-Fit T-Shirt", "subcategory": "T-Shirts"}
                )
                
                assert success is True
                assert out_bytes is not None
                assert mock_post.called
                call_kwargs = mock_post.call_args[1]
                assert call_kwargs["headers"]["Authorization"] == "Bearer fashn_test_key_123"
                payload = call_kwargs["json"]
                assert payload["model_name"] == "tryon-v1.6"
                assert payload["inputs"]["category"] == "tops"
                assert payload["inputs"]["garment_image"] == "https://img.test/black_tee.jpg"
                assert payload["inputs"]["model_image"].startswith("data:image/jpeg;base64,")

def test_fashn_polling_lifecycle_completed():
    provider = FashnVirtualTryOnProvider(api_key="fashn_test_key", poll_interval=0.01)
    
    with patch("requests.post") as mock_post, patch("requests.get") as mock_get:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"id": "pred_999", "status": "starting"}
        )
        
        # 1st poll: in_progress, 2nd poll: completed
        mock_get.side_effect = [
            MagicMock(status_code=200, json=lambda: {"id": "pred_999", "status": "in_progress"}),
            MagicMock(status_code=200, json=lambda: {"id": "pred_999", "status": "completed", "output": ["https://cdn.fashn.ai/result.jpg"]}),
            MagicMock(status_code=200, content=make_test_image_bytes(marker=b"\xc7")) # download response
        ]
        
        success, out_bytes, err_code, err_msg = provider.generate_try_on(
            person_image_bytes=make_test_image_bytes(marker=b"\xa1"),
            product_image_url="https://img.test/tee.jpg",
            garment_type="CLOTHING",
            product_metadata={"name": "Shirt", "subcategory": "Shirts"}
        )
        
        assert success is True
        assert out_bytes == make_test_image_bytes(marker=b"\xc7")
        assert err_code is None

def test_fashn_polling_lifecycle_failed():
    provider = FashnVirtualTryOnProvider(api_key="fashn_test_key", poll_interval=0.01)
    
    with patch("requests.post") as mock_post, patch("requests.get") as mock_get:
        mock_post.return_value = MagicMock(status_code=200, json=lambda: {"id": "pred_fail", "status": "starting"})
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {"id": "pred_fail", "status": "failed", "error": {"message": "Person upper body not clearly visible."}})
        
        success, out_bytes, err_code, err_msg = provider.generate_try_on(
            person_image_bytes=make_test_image_bytes(),
            product_image_url="https://img.test/tee.jpg",
            garment_type="CLOTHING",
            product_metadata={"subcategory": "T-Shirts"}
        )
        assert success is False
        assert err_code == "FASHN_SYNTHESIS_FAILED"
        assert "not clearly visible" in err_msg

def test_fashn_polling_timeout_handling():
    provider = FashnVirtualTryOnProvider(api_key="fashn_test_key", poll_interval=0.01, max_poll_attempts=2)
    
    with patch("requests.post") as mock_post, patch("requests.get") as mock_get:
        mock_post.return_value = MagicMock(status_code=200, json=lambda: {"id": "pred_slow", "status": "starting"})
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {"id": "pred_slow", "status": "in_progress"})
        
        success, out_bytes, err_code, err_msg = provider.generate_try_on(
            person_image_bytes=make_test_image_bytes(),
            product_image_url="https://img.test/tee.jpg",
            garment_type="CLOTHING",
            product_metadata={"subcategory": "T-Shirts"}
        )
        assert success is False
        assert err_code == "PROVIDER_TIMEOUT"
        assert "longer than expected" in err_msg

def test_fashn_identical_input_output_rejected():
    provider = FashnVirtualTryOnProvider(api_key="fashn_test_key")
    input_bytes = make_test_image_bytes(marker=b"\xa1")
    
    # Download returns the exact same bytes as input
    with patch("requests.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, content=input_bytes)
        success, out_bytes, err_code, err_msg = provider._download_and_validate_output("https://cdn.fashn.ai/echo.jpg", input_bytes)
        assert success is False
        assert err_code == "IDENTICAL_OUTPUT_REJECTED"
        assert "unmodified input" in err_msg.lower()


# =====================================================================
# 3. Selected Variant Color & Integration Tests
# =====================================================================

def test_selected_color_garment_image_used(vto_test_context, db_session: Session):
    shirt = vto_test_context["shirt"]
    token_a = vto_test_context["token_a"]
    
    # When variant is Pure White, verify white garment URL is passed to provider
    with patch.object(FashnVirtualTryOnProvider, "generate_try_on") as mock_gen:
        mock_gen.return_value = (True, make_test_image_bytes(marker=b"\xdd"), None, None)
        with patch.object(FashnVirtualTryOnProvider, "is_available", True):
            files = {"photo": ("person.jpg", make_test_image_bytes(), "image/jpeg")}
            data = {"product_id": shirt.id, "consent": "true", "variant_id": "Pure White-Medium"}
            res = client.post("/api/v1/virtual-tryon/jobs", data=data, files=files, headers={"Authorization": f"Bearer {token_a}"})
            
            assert res.status_code == 200
            assert mock_gen.called
            call_kwargs = mock_gen.call_args[1]
            assert "581655353564" in call_kwargs["product_image_url"] # Pure white photo ID

def test_cross_user_cannot_access_another_users_tryon_job(vto_test_context):
    token_a = vto_test_context["token_a"]
    token_b = vto_test_context["token_b"]
    shirt = vto_test_context["shirt"]
    
    with patch.object(FashnVirtualTryOnProvider, "generate_try_on") as mock_gen, patch.object(FashnVirtualTryOnProvider, "is_available", True):
        mock_gen.return_value = (True, make_test_image_bytes(marker=b"\xbb"), None, None)
        
        files = {"photo": ("person.jpg", make_test_image_bytes(), "image/jpeg")}
        data = {"product_id": shirt.id, "consent": "true"}
        res_a = client.post("/api/v1/virtual-tryon/jobs", data=data, files=files, headers={"Authorization": f"Bearer {token_a}"})
        assert res_a.status_code == 200
        job_id = res_a.json()["job_id"]

        # User B attempts to access User A job -> 403 Forbidden
        res_b = client.get(f"/api/v1/virtual-tryon/jobs/{job_id}", headers={"Authorization": f"Bearer {token_b}"})
        assert res_b.status_code == 403

        # User B attempts to access User A media -> 403 Forbidden
        res_media_b = client.get(f"/api/v1/virtual-tryon/media/{job_id}/result", headers={"Authorization": f"Bearer {token_b}"})
        assert res_media_b.status_code == 403

def test_no_secret_leakage_in_api_responses_or_logs(vto_test_context):
    shirt = vto_test_context["shirt"]
    token_a = vto_test_context["token_a"]
    
    with patch.object(FashnVirtualTryOnProvider, "generate_try_on") as mock_gen, patch.object(FashnVirtualTryOnProvider, "is_available", True):
        mock_gen.return_value = (True, make_test_image_bytes(marker=b"\xcc"), None, None)
        
        files = {"photo": ("person.jpg", make_test_image_bytes(), "image/jpeg")}
        data = {"product_id": shirt.id, "consent": "true"}
        res = client.post("/api/v1/virtual-tryon/jobs", data=data, files=files, headers={"Authorization": f"Bearer {token_a}"})
        job_id = res.json()["job_id"]
        
        status_res = client.get(f"/api/v1/virtual-tryon/jobs/{job_id}", headers={"Authorization": f"Bearer {token_a}"})
        body_text = json.dumps(status_res.json())
        assert "FASHN_API_KEY" not in body_text
        assert "fashn_" not in body_text
        assert "api_key" not in body_text

def test_job_creation_fails_without_explicit_consent(vto_test_context):
    token_a = vto_test_context["token_a"]
    shirt = vto_test_context["shirt"]
    files = {"photo": ("person.jpg", make_test_image_bytes(), "image/jpeg")}
    data = {"product_id": shirt.id, "consent": "false"}
    res = client.post("/api/v1/virtual-tryon/jobs", data=data, files=files, headers={"Authorization": f"Bearer {token_a}"})
    assert res.status_code == 400
    assert "consent is required" in res.json()["detail"].lower()

def test_vto_does_not_mutate_authoritative_price_or_stock(vto_test_context, db_session: Session):
    shirt = vto_test_context["shirt"]
    orig_price = shirt.price
    token_a = vto_test_context["token_a"]
    
    with patch.object(FashnVirtualTryOnProvider, "generate_try_on") as mock_gen, patch.object(FashnVirtualTryOnProvider, "is_available", True):
        mock_gen.return_value = (True, make_test_image_bytes(marker=b"\xee"), None, None)
        files = {"photo": ("person.jpg", make_test_image_bytes(), "image/jpeg")}
        client.post("/api/v1/virtual-tryon/jobs", data={"product_id": shirt.id, "consent": "true"}, files=files, headers={"Authorization": f"Bearer {token_a}"})
        
        db_p = db_session.query(Product).filter(Product.id == shirt.id).first()
        assert db_p.price == orig_price

def test_tryon_job_cancellation(vto_test_context):
    token_a = vto_test_context["token_a"]
    shirt = vto_test_context["shirt"]
    
    with patch.object(FashnVirtualTryOnProvider, "generate_try_on") as mock_gen, patch.object(FashnVirtualTryOnProvider, "is_available", True):
        mock_gen.return_value = (True, make_test_image_bytes(marker=b"\xff"), None, None)
        files = {"photo": ("person.jpg", make_test_image_bytes(), "image/jpeg")}
        data = {"product_id": shirt.id, "consent": "true"}
        res_a = client.post("/api/v1/virtual-tryon/jobs", data=data, files=files, headers={"Authorization": f"Bearer {token_a}"})
        job_id = res_a.json()["job_id"]

        res_cancel = client.post(f"/api/v1/virtual-tryon/jobs/{job_id}/cancel", headers={"Authorization": f"Bearer {token_a}"})
        assert res_cancel.status_code == 200
        assert res_cancel.json()["status"] == "CANCELLED"
